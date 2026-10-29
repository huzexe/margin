"""Margin: FastAPI app. Serves the pages, the static files and the JSON API."""

import asyncio
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import auth, config, db, lifecycle
from .routes import notes, settings, subjects
from .services import pdf
from .services.llm import LLMError
from .services.pdf import PdfError


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    watch = asyncio.create_task(lifecycle.watchdog()) if config.AUTO_STOP else None
    yield
    if watch:
        watch.cancel()
    await pdf.shutdown()


app = FastAPI(title="Margin", lifespan=lifespan, docs_url=None, redoc_url=None)

# Only answer requests addressed to this computer (blocks DNS-rebinding tricks)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=auth.allowed_hosts())

OPEN_PATHS = ("/unlock", "/api/unlock", "/static/")  # reachable before entering the PIN


@app.middleware("http")
async def require_pin(request: Request, call_next):
    """Other devices must unlock with the PIN; this computer never has to."""
    path = request.url.path
    if auth.is_allowed(request) or path.startswith(OPEN_PATHS):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Locked. Reload the page and enter the PIN."}, status_code=401)
    return RedirectResponse(f"/unlock?next={quote(path)}", status_code=303)

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; "
    "frame-src 'self' blob:; object-src 'none'; base-uri 'none'; "
    "frame-ancestors 'self'; form-action 'self'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# Errors always come back as {"detail": "<plain message>"} so the page can show them
@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(LLMError)
async def llm_error(request: Request, exc: LLMError):
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    return JSONResponse({"detail": exc.message}, status_code=exc.status, headers=headers)


@app.exception_handler(PdfError)
async def pdf_error(request: Request, exc: PdfError):
    return JSONResponse({"detail": exc.message}, status_code=500)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    msg = str(first.get("msg", "Invalid input.")).removeprefix("Value error, ")
    field = first.get("loc", [])[-1] if first.get("loc") else None
    if first.get("type") == "string_too_long" and field:
        msg = f"{str(field).replace('_', ' ').capitalize()} is too long."
    return JSONResponse({"detail": msg}, status_code=422)


app.include_router(subjects.router)
app.include_router(notes.router)
app.include_router(notes.tags_router)
app.include_router(settings.router)


def page(name: str) -> FileResponse:
    return FileResponse(config.STATIC_DIR / name, headers={"Cache-Control": "no-cache"})


# ---------- Running only while in use ----------

@app.post("/api/heartbeat", status_code=204, include_in_schema=False)
def heartbeat():
    lifecycle.touch()


class StopIn(BaseModel):
    stop: bool  # a JSON body means other websites can't send this request from your browser


@app.post("/api/shutdown", include_in_schema=False)
def shutdown(body: StopIn, request: Request):
    """Used by 'Quit Margin'. Only accepted from this computer."""
    if not auth.is_this_computer(request):
        raise HTTPException(403, "Only possible on the computer running Margin.")
    if body.stop:
        lifecycle.request_exit()
    return {"ok": True}


# ---------- Phone access ----------

class PinIn(BaseModel):
    pin: str = Field(max_length=100)


@app.post("/api/unlock", include_in_schema=False)
def unlock(body: PinIn, request: Request):
    if not config.PHONE_ACCESS:
        raise HTTPException(403, "Phone access is turned off.")
    device = request.client.host if request.client else "?"
    ok, error = auth.check_pin(device, body.pin)
    if not ok:
        raise HTTPException(401, error)
    response = JSONResponse({"ok": True})
    response.set_cookie(auth.COOKIE, auth.make_cookie(), max_age=auth.COOKIE_DAYS * 86400,
                        httponly=True, samesite="strict", path="/")
    return response


@app.get("/api/phone", include_in_schema=False)
def phone_status(request: Request):
    ip = auth.lan_address() if config.PHONE_ACCESS else None
    return {
        "enabled": config.PHONE_ACCESS,
        "pin_set": bool(config.PIN),
        "url": f"http://{ip}:{config.PORT}" if ip else None,
        "this_computer": auth.is_this_computer(request),
    }


@app.post("/api/phone/sign-out-all", include_in_schema=False)
def sign_out_phones(request: Request):
    if not auth.is_this_computer(request):
        raise HTTPException(403, "Only possible on the computer running Margin.")
    auth.rotate_secret()
    return {"ok": True}


@app.get("/unlock", include_in_schema=False)
def unlock_page(request: Request):
    if auth.is_allowed(request):
        return RedirectResponse("/", status_code=303)
    return page("unlock.html")


@app.get("/", include_in_schema=False)
def library_page():
    return page("index.html")


@app.get("/notes/new", include_in_schema=False)
@app.get("/notes/{note_id:int}", include_in_schema=False)
def note_page(note_id: int | None = None):
    return page("note.html")


@app.get("/settings", include_in_schema=False)
def settings_page():
    return page("settings.html")


@app.get("/notes/{note_id:int}/export", include_in_schema=False)
def export_page(note_id: int):
    return page("export.html")


@app.get("/notes/{note_id:int}/print", include_in_schema=False)
def print_page(note_id: int):
    return page("print.html")


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
