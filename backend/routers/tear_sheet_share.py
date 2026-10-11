"""Tear Sheet PDF — Research → Tear Sheet → Download PDF.

  GET /api/tear-sheet/{symbol}/pdf     the tear sheet as a PDF download

Uses routers.tear_sheet.load_tear_sheet, i.e. the same cached data the page shows, and
tear_sheet_pdf.build_pdf, so the file matches what was on screen.
"""
import asyncio
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from routers.tear_sheet import load_tear_sheet
from routers.tear_sheet_peers import cached_peers
from tear_sheet_pdf import build_pdf

router = APIRouter()

_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-^=]{1,12}$")


def pdf_filename(sheet: dict) -> str:
    return f"{sheet['symbol']}_TearSheet_{sheet.get('asOf', '')}.pdf"


@router.get("/api/tear-sheet/{symbol}/pdf")
async def tear_sheet_pdf(symbol: str):
    sym = symbol.upper().strip()
    if not _SYMBOL_RE.match(sym):
        raise HTTPException(400, "Invalid ticker symbol")
    sheet = await load_tear_sheet(sym)
    if sheet.get("error"):
        raise HTTPException(404, sheet["error"])
    peers = cached_peers(sym)                       # included only if the page already loaded it; a PDF never triggers peer downloads
    if peers:
        sheet = {**sheet, "peers": peers}
    loop = asyncio.get_event_loop()
    pdf = await loop.run_in_executor(None, lambda: build_pdf(sheet))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{pdf_filename(sheet)}"'})
