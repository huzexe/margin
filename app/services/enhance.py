"""Enhance: the reply format, and conversion into editor blocks."""

import hashlib
import html
import json
import re
from typing import Literal

from pydantic import BaseModel, Field

# ---------- Reply format requested from the model ----------

BlockType = Literal[
    "paragraph", "subheading", "bullets", "steps", "definition",
    "formula", "example", "code", "table", "diagram", "verify",
]


class TableData(BaseModel):
    header: list[str]
    rows: list[list[str]]


class Block(BaseModel):
    type: BlockType
    # Required (not optional) so the model can't skip it, e.g. a definition's meaning
    text: str = Field(description=(
        "paragraph/subheading/example/verify: the text. definition: the meaning of the term. "
        "formula: one line explaining the symbols. diagram: a short caption. "
        "Empty string for bullets, steps, code and table."))
    term: str | None = Field(None, description="definition only: the term being defined")
    items: list[str] | None = Field(None, description="bullets/steps only: one entry per point")
    latex: str | None = Field(None, description="formula only: LaTeX without $ signs")
    code: str | None = Field(None, description="code only: the snippet")
    language: str | None = Field(None, description="code only: programming language")
    table: TableData | None = Field(None, description="table only")
    mermaid: str | None = Field(None, description="diagram only: Mermaid 11 code")


class Section(BaseModel):
    heading: str
    blocks: list[Block]


class Card(BaseModel):
    question: str
    answer: str


class EnhancedNotes(BaseModel):
    sections: list[Section] = Field(min_length=1)
    key_takeaways: list[str]
    flashcards: list[Card] | None = None


class EnhanceOptions(BaseModel):
    simplify: bool = False
    diagrams: bool = False
    applications: bool = False
    flashcards: bool = False
    detail: Literal["concise", "standard", "detailed"] = "standard"


class DiagramFix(BaseModel):
    mermaid: str = Field(description="the corrected Mermaid 11 code")


# ---------- Conversion to editor blocks ----------

_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")


def inline(text: str | None) -> str:
    """Escape text, then turn **bold**, *italic* and `code` into safe HTML."""
    if not text:
        return ""
    parts = _CODE.split(text)  # odd indexes are code spans
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(f'<code class="inline-code">{html.escape(part)}</code>')
        else:
            s = html.escape(part, quote=False)
            s = _BOLD.sub(r"<b>\1</b>", s)
            s = _ITALIC.sub(r"<i>\1</i>", s)
            out.append(s)
    return "".join(out).strip()


def heading(text: str | None) -> str:
    """Headings are plain text: drop Markdown markers and escape."""
    return html.escape(re.sub(r"\*\*|`|(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", text or ""), quote=False).strip()


def _list(items: list[str] | None, ordered: bool) -> dict | None:
    items = [i for i in (items or []) if i and i.strip()]
    if not items:
        return None
    return {
        "type": "list",
        "data": {
            "style": "ordered" if ordered else "unordered",
            "meta": {"counterType": "numeric"} if ordered else {},
            "items": [{"content": inline(i), "meta": {}, "items": []} for i in items],
        },
    }


def _convert_block(b: Block) -> dict | None:
    t = b.type
    if t == "paragraph" and b.text:
        return {"type": "paragraph", "data": {"text": inline(b.text)}}
    if t == "subheading" and b.text:
        return {"type": "header", "data": {"text": heading(b.text), "level": 3}}
    if t in ("bullets", "steps"):
        return _list(b.items, ordered=t == "steps")
    if t == "definition" and (b.term or b.text):
        meaning = b.text or " ".join(b.items or [])
        if b.term and not meaning:
            return None  # a term with no meaning would be an empty definition box
        term = f"<b>{inline(b.term)}</b>: " if b.term else ""
        return {"type": "callout", "data": {"kind": "definition", "text": term + inline(meaning)}}
    if t == "formula" and b.latex:
        latex = b.latex.strip().strip("$").strip()
        return {"type": "formula", "data": {"latex": latex, "text": inline(b.text)}}
    if t in ("example", "verify") and b.text:
        return {"type": "callout", "data": {"kind": t, "text": inline(b.text)}}
    if t == "code" and b.code:
        return {"type": "code", "data": {"code": b.code.rstrip()}}
    if t == "diagram" and b.mermaid and b.mermaid.strip():
        code = re.sub(r"^```(?:mermaid)?\s*|\s*```$", "", b.mermaid.strip())  # drop stray code fences
        caption = re.sub(r"\*\*|`", "", b.text or "").strip()  # plain text, shown with textContent
        return {"type": "diagram", "data": {"code": code, "caption": caption}}
    if t == "table" and b.table and b.table.header:
        width = len(b.table.header)
        rows = [r[:width] + [""] * (width - len(r)) for r in b.table.rows if any(c.strip() for c in r)]
        content = [[inline(c) for c in row] for row in [b.table.header, *rows]]
        return {"type": "table", "data": {"withHeadings": True, "stretched": False, "content": content}}
    return None  # empty or malformed block: skip it rather than show something broken


def section_blocks(section: Section) -> list[dict]:
    """One section as editor blocks: its heading followed by its content (empty if no content)."""
    converted = [c for c in (_convert_block(b) for b in section.blocks) if c]
    if not converted:
        return []
    return [{"type": "header", "data": {"text": heading(section.heading), "level": 2}}, *converted]


def to_editor(doc: EnhancedNotes) -> dict:
    blocks: list[dict] = []
    for section in doc.sections:
        blocks.extend(section_blocks(section))

    takeaways = [t for t in doc.key_takeaways if t.strip()]
    if takeaways:
        items = "".join(f"<li>{inline(t)}</li>" for t in takeaways)
        blocks.append({"type": "header", "data": {"text": "Key takeaways", "level": 2}})
        blocks.append({"type": "callout", "data": {"kind": "takeaway", "text": f"<ul>{items}</ul>"}})

    cards = [c for c in (doc.flashcards or []) if c.question.strip() and c.answer.strip()]
    if cards:
        blocks.append({"type": "header", "data": {"text": "Flashcards", "level": 2}})
        blocks.append({
            "type": "flashcards",
            "data": {"cards": [{"question": inline(c.question), "answer": inline(c.answer)} for c in cards]},
        })

    return {"blocks": blocks}


# ---------- Helpers used when saving ----------

ALLOWED_BLOCKS = {"paragraph", "header", "list", "table", "code", "callout", "formula", "flashcards", "diagram"}
_INLINE_TAGS = re.compile(r"</?(?:b|i|u|em|strong|code|mark|sub|sup|a)(?:\s[^>]*)?>", re.I)
_TAGS = re.compile(r"<[^>]+>")


def _plain(value) -> str:
    """HTML to text: formatting tags vanish, other tags (li, br…) become spaces."""
    if not isinstance(value, str):
        return ""
    text = _TAGS.sub(" ", _INLINE_TAGS.sub("", value))
    return re.sub(r"[ \t]+", " ", html.unescape(text)).strip()


def _walk_list(items) -> list[str]:
    out = []
    for item in items or []:
        if isinstance(item, dict):
            out.append(_plain(item.get("content")))
            out.extend(_walk_list(item.get("items")))
        else:
            out.append(_plain(item))
    return out


def content_text(content: dict | None) -> str:
    """Plain text of the enhanced notes, for search."""
    if not content:
        return ""
    parts: list[str] = []
    for block in content.get("blocks", []):
        data = block.get("data") or {}
        kind = block.get("type")
        if kind == "list":
            parts.extend(_walk_list(data.get("items")))
        elif kind == "table":
            parts.extend(_plain(c) for row in data.get("content") or [] for c in row)
        elif kind == "flashcards":
            for card in data.get("cards") or []:
                parts += [_plain(card.get("question")), _plain(card.get("answer"))]
        elif kind == "diagram":
            parts += [_plain(data.get("caption")), *diagram_labels(data.get("code"))]
        else:
            parts += [_plain(data.get(k)) for k in ("text", "code", "latex")]
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()


_LABEL = re.compile(r'"([^"\n]{1,120})"|\[([^\[\]"\n]{1,120})\]|\(\(?([^()"\n]{1,120})\)?\)|\{([^{}"\n]{1,120})\}')


def diagram_labels(code) -> list[str]:
    """Readable labels inside Mermaid code (for search)."""
    if not isinstance(code, str):
        return []
    return [next(g for g in m.groups() if g) for m in _LABEL.finditer(code)]


def block_heading(block: dict) -> str:
    """Plain text of a heading block ('' for other blocks)."""
    return _plain((block.get("data") or {}).get("text")) if block.get("type") == "header" else ""


def outline_except(content: dict | None, skip_heading: str) -> list[str]:
    """Section headings and diagram captions of the other sections, so a rewritten section doesn't repeat them."""
    items: list[str] = []
    current = None
    for block in (content or {}).get("blocks", []):
        data = block.get("data") or {}
        if block.get("type") == "header" and data.get("level") == 2:
            current = _plain(data.get("text"))
            if current and current != skip_heading and current not in ("Key takeaways", "Flashcards"):
                items.append(f"Section: {current}")
        elif block.get("type") == "diagram" and current != skip_heading:
            caption = _plain(data.get("caption"))
            items.append(f"Diagram: {caption}" if caption else "Diagram (no caption)")
    return items[:40]


def blocks_to_text(blocks: list[dict]) -> str:
    """Editor blocks as readable text, used to show the model the current version of a section."""
    lines: list[str] = []
    for block in blocks:
        data = block.get("data") or {}
        kind = block.get("type")
        if kind == "header":
            lines.append(("## " if data.get("level") == 2 else "### ") + _plain(data.get("text")))
        elif kind == "list":
            ordered = data.get("style") == "ordered"
            lines += [f"{'1.' if ordered else '-'} {t}" for t in _walk_list(data.get("items"))]
        elif kind == "callout":
            lines.append(f"[{data.get('kind', 'note')}] {_plain(data.get('text'))}")
        elif kind == "formula":
            lines.append(f"[formula] {data.get('latex', '')} | {_plain(data.get('text'))}")
        elif kind == "code":
            lines.append(f"```\n{data.get('code', '')}\n```")
        elif kind == "table":
            lines += [" | ".join(_plain(c) for c in row) for row in data.get("content") or []]
        elif kind == "diagram":
            lines.append(f"[diagram: {_plain(data.get('caption'))}]\n{data.get('code', '')}")
        elif kind == "flashcards":
            lines += [f"Q: {_plain(c.get('question'))} A: {_plain(c.get('answer'))}" for c in data.get("cards") or []]
        else:
            lines.append(_plain(data.get("text")))
    return "\n".join(line for line in lines if line.strip())


def validate_content(content: dict) -> dict:
    """Check the editor JSON has the expected shape before it is saved."""
    blocks = content.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("Enhanced notes are in an unexpected format.")
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") not in ALLOWED_BLOCKS or not isinstance(block.get("data"), dict):
            raise ValueError("Enhanced notes contain an unsupported block.")
    return {"blocks": blocks, "time": content.get("time"), "version": content.get("version")}


def source_hash(*, title: str, topic: str, subject: str | None, rough_text: str, options: EnhanceOptions) -> str:
    payload = json.dumps(
        {"title": title, "topic": topic, "subject": subject, "rough": rough_text, "options": options.model_dump()},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
