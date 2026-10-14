import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz
from PIL import Image

from schemas import ReadResult

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PAGES = 5
MIN_ALNUM = 20
OCR_TIMEOUT = 60

_EXT_KIND = {
    ".pdf": "pdf",
    ".png": "png",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
}

_WIN_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

# Status values:
# ok, insufficient_text, empty_file, too_large, too_many_pages,
# unsupported_type, corrupted, ocr_unavailable, ocr_failed,
# unreadable_file.
# Every status except "ok" sets needs_review=True.


def _fail(status: str, detail: str) -> ReadResult:
    return ReadResult(
        status=status,
        needs_review=True,
        detail=detail,
    )


def _sniff(data: bytes):
    if data.startswith(b"%PDF"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


def _enough(text: str) -> bool:
    return sum(ch.isalnum() for ch in text) >= MIN_ALNUM


def find_tesseract():
    env = os.getenv("TESSERACT_CMD")
    if env and Path(env).is_file():
        return env

    found = shutil.which("tesseract")
    if found:
        return found

    for path in _WIN_PATHS:
        if Path(path).is_file():
            return path

    return None


def _ocr(image_bytes: bytes, suffix: str):
    """Return (text, None) or (None, failure ReadResult)."""
    exe = find_tesseract()

    if exe is None:
        return None, _fail(
            "ocr_unavailable",
            "Tesseract OCR is not installed.",
        )

    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"page{suffix}"
            path.write_bytes(image_bytes)

            proc = subprocess.run(
                [
                    exe,
                    str(path),
                    "stdout",
                    "-l", "eng",
                    "--psm", "6",
                ],
                capture_output=True,
                timeout=OCR_TIMEOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
    except subprocess.TimeoutExpired:
        return None, _fail("ocr_failed", "OCR timed out.")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, _fail("ocr_failed", "OCR could not be run.")

    if proc.returncode != 0:
        return None, _fail("ocr_failed", "OCR returned an error.")

    return proc.stdout, None


def _ocr_result(text: str, pages: int) -> ReadResult:
    text = text.strip()

    if _enough(text):
        return ReadResult(
            text=text,
            method="ocr",
            status="ok",
            needs_review=False,
            detail="Read with OCR.",
            pages=pages,
        )

    return ReadResult(
        text=text,
        method="ocr",
        status="insufficient_text",
        needs_review=True,
        detail="OCR found too little readable text.",
        pages=pages,
    )


def _read_pdf(data: bytes) -> ReadResult:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        return _fail("corrupted", "The PDF could not be opened.")

    try:
        if doc.needs_pass:
            return _fail(
                "unsupported_type",
                "The PDF is password protected.",
            )

        if doc.page_count == 0:
            return _fail("corrupted", "The PDF has no pages.")

        # Reject oversized PDFs before reading any document text.
        if doc.page_count > MAX_PAGES:
            return ReadResult(
                status="too_many_pages",
                needs_review=True,
                detail=(
                    f"The PDF has {doc.page_count} pages; "
                    f"the limit is {MAX_PAGES}."
                ),
                pages=doc.page_count,
            )

        pages = doc.page_count
        text = "\n".join(
            doc[i].get_text() for i in range(pages)
        ).strip()

        if _enough(text):
            return ReadResult(
                text=text,
                method="pdf_text",
                status="ok",
                needs_review=False,
                detail="Read from PDF text.",
                pages=pages,
            )

        # No usable text layer: render pages and use OCR.
        parts = []

        for i in range(pages):
            png = doc[i].get_pixmap(
                matrix=fitz.Matrix(2, 2)
            ).tobytes("png")

            out, failure = _ocr(png, ".png")

            if failure is not None:
                return failure

            parts.append(out)

        return _ocr_result("\n".join(parts), pages)

    except Exception:
        return _fail("corrupted", "The PDF could not be read.")

    finally:
        doc.close()


def _read_image(data: bytes, kind: str) -> ReadResult:
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except Exception:
        return _fail("corrupted", "The image could not be decoded.")

    suffix = ".png" if kind == "png" else ".jpg"
    text, failure = _ocr(data, suffix)

    if failure is not None:
        return failure

    return _ocr_result(text, 1)


def read_document(data: bytes, filename: str) -> ReadResult:
    if not data:
        return _fail("empty_file", "The file is empty.")

    if len(data) > MAX_BYTES:
        return _fail(
            "too_large",
            "The file is larger than 5 MB.",
        )

    expected = _EXT_KIND.get(Path(filename).suffix.lower())

    if expected is None:
        return _fail(
            "unsupported_type",
            "Only PDF, PNG and JPG files are supported.",
        )

    if _sniff(data) != expected:
        return _fail(
            "unsupported_type",
            "The file content does not match its extension.",
        )

    if expected == "pdf":
        return _read_pdf(data)

    return _read_image(data, expected)


def read_path(path) -> ReadResult:
    path = Path(path)

    try:
        data = path.read_bytes()
    except OSError:
        return _fail(
            "unreadable_file",
            "The file could not be opened.",
        )

    return read_document(data, path.name)