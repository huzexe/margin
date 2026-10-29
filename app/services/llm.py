"""Text-generation provider (Google Gemini).

Everything provider-specific lives in this file. To switch provider later,
replace generate_json() and keep its signature and LLMError messages.
"""

import logging

from pydantic import BaseModel, ValidationError

from .. import config

log = logging.getLogger("margin.llm")


class LLMError(Exception):
    """Error with a message that is safe to show in the app."""

    def __init__(self, message: str, status: int = 502, retry_after: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retry_after = retry_after


MSG_NO_KEY = "The service key isn't set up. Add it to the .env file (see README, step 2) and restart Margin."
MSG_BAD_KEY = "The service key was rejected. Check the key in the .env file (see README, step 2) and restart Margin."
MSG_BUSY = "Service is busy. Please try again in a minute."
MSG_LIMIT = "Daily limit reached. Please try again later."
MSG_TIMEOUT = "This took too long. Please try again."
MSG_OFFLINE = "Couldn't connect. Check your internet connection and try again."
MSG_FAILED = "Couldn't process these notes. Please try again."
MSG_BLOCKED = "These notes couldn't be processed. Try rewording them."

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types

        if not config.GEMINI_API_KEY:
            raise LLMError(MSG_NO_KEY, status=503)
        _client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=config.LLM_TIMEOUT_SECONDS * 1000),
        )
    return _client


def _map_api_error(err) -> LLMError:
    code = getattr(err, "code", None)
    text = str(getattr(err, "message", "") or err).lower()
    if code in (401, 403) or "api key" in text or "api_key" in text:
        return LLMError(MSG_BAD_KEY, status=503)
    if code == 429:
        daily = "per day" in text or "perday" in text or "daily" in text
        return LLMError(MSG_LIMIT if daily else MSG_BUSY, status=429, retry_after=None if daily else 60)
    if code in (500, 502, 503, 504):
        return LLMError(MSG_BUSY, status=503, retry_after=30)
    return LLMError(MSG_FAILED)


def _call(model: str, system: str, prompt: str, schema: type[BaseModel], max_tokens: int, temperature: float):
    from google.genai import types

    return _get_client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )


def generate_json(
    system: str,
    prompt: str,
    schema: type[BaseModel],
    *,
    max_tokens: int = 16_000,
    temperature: float = 0.4,
) -> BaseModel:
    """Ask the model for JSON matching `schema` and return it parsed and validated.

    Tries the main model; if it is overloaded, tries the fallback model once.
    If the reply doesn't match the schema, asks once more before giving up.
    """
    from google.genai import errors

    models = [config.GEMINI_MODEL]
    if config.GEMINI_FALLBACK_MODEL and config.GEMINI_FALLBACK_MODEL != config.GEMINI_MODEL:
        models.append(config.GEMINI_FALLBACK_MODEL)

    last_error: LLMError | None = None
    for model in models:
        for attempt in range(2):  # second attempt only for unusable replies
            try:
                response = _call(model, system, prompt, schema, max_tokens, temperature)
            except errors.APIError as e:
                log.warning("model %s failed: %s %s", model, e.code, e.message)
                last_error = _map_api_error(e)
                if last_error.status == 503 and last_error.message == MSG_BUSY:
                    break  # overloaded: try the fallback model
                raise last_error
            except LLMError:
                raise
            except Exception as e:  # network errors, timeouts
                log.warning("model %s request error: %r", model, e)
                name = type(e).__name__.lower()
                raise LLMError(MSG_TIMEOUT if "timeout" in name else MSG_OFFLINE, status=504)

            feedback = getattr(response, "prompt_feedback", None)
            if feedback is not None and getattr(feedback, "block_reason", None):
                raise LLMError(MSG_BLOCKED, status=422)

            parsed = getattr(response, "parsed", None)
            try:
                if isinstance(parsed, schema):
                    return parsed
                return schema.model_validate_json(response.text or "")
            except (ValidationError, ValueError) as e:
                reason = response.candidates[0].finish_reason if response.candidates else None
                log.warning("model %s returned unusable JSON (finish=%s): %s", model, reason, e)
                last_error = LLMError(MSG_FAILED)
                continue

    raise last_error or LLMError(MSG_FAILED)
