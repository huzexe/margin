"""PDF export: a headless browser prints the note's /print page to an A4 PDF.

It uses a browser that is already installed (Google Chrome, Microsoft Edge or Chromium),
run invisibly, so nothing extra has to be downloaded. One browser is started on first use
and reused; one PDF is made at a time.
"""

import asyncio
import io
import logging
import os
import re
import shutil
import sys
import unicodedata
from typing import Literal
from urllib.parse import urlencode

from pydantic import BaseModel

log = logging.getLogger("margin.pdf")

MARGINS_MM = {"narrow": 12, "normal": 20, "wide": 28}
FOOTER_MM = 16  # room for the page-number footer
READY_TIMEOUT_MS = 45_000


class PdfError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PdfSettings(BaseModel):
    toc: bool = True
    flashcards: bool = True
    rough: bool = False
    size: Literal["small", "medium", "large"] = "medium"
    margins: Literal["narrow", "normal", "wide"] = "normal"

    def query(self) -> str:
        return urlencode({k: (int(v) if isinstance(v, bool) else v) for k, v in self.model_dump().items()})


_playwright = None
_browser = None
_lock = asyncio.Lock()


NO_BROWSER = (
    "PDF export needs Google Chrome, Microsoft Edge or Chromium. Install one of them "
    "(they're free), then try again."
)


def launch_options() -> list[dict]:
    """Browsers to try, in order. Each entry is passed to Playwright's chromium.launch()."""
    options: list[dict] = []
    custom = os.environ.get("MARGIN_PDF_BROWSER", "").strip()  # optional path to a specific browser
    if custom:
        options.append({"executable_path": custom})
    options += [{"channel": "chrome"}, {"channel": "msedge"}]  # standard install locations, any system
    for name in ("chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            options.append({"executable_path": path})
    if sys.platform == "darwin":
        options.append({"executable_path": "/Applications/Chromium.app/Contents/MacOS/Chromium"})
    options.append({})  # Playwright's own engine, only present if an older Margin version downloaded it
    return options


async def _get_browser():
    global _playwright, _browser
    if _browser and _browser.is_connected():
        return _browser
    from playwright.async_api import Error, async_playwright

    if _playwright is None:
        _playwright = await async_playwright().start()
    for options in launch_options():
        try:
            _browser = await _playwright.chromium.launch(**options)
            log.info("PDF browser: %s", options or "Playwright's own")
            return _browser
        except Error as e:
            log.debug("PDF browser %s not usable: %s", options, str(e).splitlines()[0])
    raise PdfError(NO_BROWSER)


async def shutdown() -> None:
    global _playwright, _browser
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()
    _browser = _playwright = None


def _footer(margin_mm: int) -> str:
    # Shown at the bottom of every page; Chromium fills .title, .pageNumber and .totalPages
    return (
        f'<div style="width:100%;margin:0 {margin_mm}mm;font-family:sans-serif;font-size:8px;color:#6B6F76;'
        'display:flex;justify-content:space-between;">'
        '<span class="title"></span>'
        '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
    )


def _norm(text: str) -> str:
    return re.sub(r"\W+", "", unicodedata.normalize("NFKC", text).lower())


def heading_pages(pdf: bytes, headings: list[str]) -> list[int]:
    """1-based page number of each heading, searching forward in order."""
    from pypdf import PdfReader

    pages = [_norm(p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages]
    result, cursor = [], 0
    for heading in headings:
        key = _norm(heading)[:60]
        found = next((i for i in range(cursor, len(pages)) if key and key in pages[i]), None)
        if found is not None:
            cursor = found
        result.append(cursor + 1)
    return result


def page_count(pdf: bytes) -> int:
    from pypdf import PdfReader

    return len(PdfReader(io.BytesIO(pdf)).pages)


async def render(base_url: str, note_id: int, settings: PdfSettings) -> bytes:
    from playwright.async_api import Error, TimeoutError as PwTimeout

    margin = MARGINS_MM[settings.margins]
    options = {
        "format": "A4",
        "print_background": True,
        "display_header_footer": True,
        "header_template": "<span></span>",
        "footer_template": _footer(margin),
        "margin": {"top": f"{margin}mm", "bottom": f"{max(margin, FOOTER_MM)}mm",
                   "left": f"{margin}mm", "right": f"{margin}mm"},
        "outline": True,  # PDF bookmarks from the headings
        "tagged": True,
    }
    url = f"{base_url.rstrip('/')}/notes/{note_id}/print?{settings.query()}"

    async with _lock:
        browser = await _get_browser()
        # bypass_csp: Playwright's wait/evaluate helpers run small scripts the page's own
        # security policy would block. Safe here: this private browser only opens our print page.
        context = await browser.new_context(bypass_csp=True)
        try:
            page = await context.new_page()
            await page.goto(url, wait_until="load")
            await page.wait_for_function("window.__printReady !== undefined", timeout=READY_TIMEOUT_MS)
            problem = await page.evaluate("window.__printReady === true ? null : String(window.__printReady)")
            if problem:
                raise PdfError(problem)

            headings = await page.evaluate("window.__tocHeadings || []")
            if not (settings.toc and headings):
                return await page.pdf(**options)

            # Table of contents with real page numbers:
            # 1) without the contents list, find which page each heading lands on
            await page.evaluate("window.__showToc(false)")
            without = await page.pdf(**options)
            found = heading_pages(without, headings)
            # 2) with the contents list, see how many extra pages it takes
            await page.evaluate("window.__showToc(true)")
            extra = page_count(await page.pdf(**options)) - page_count(without)
            # 3) fill in the numbers (fixed-width slots, so nothing moves) and print
            await page.evaluate("pages => window.__setTocPages(pages)", [p + extra for p in found])
            return await page.pdf(**options)
        except PwTimeout:
            raise PdfError("Making the PDF took too long. Please try again.")
        except Error as e:
            log.warning("PDF render failed: %s", e)
            raise PdfError("Couldn't create the PDF. Please try again.")
        finally:
            await context.close()


def filename(title: str) -> str:
    base = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE).strip()
    base = re.sub(r"[\s_]+", "-", base)[:80].strip("-")
    return f"{base or 'Margin-note'}.pdf"
