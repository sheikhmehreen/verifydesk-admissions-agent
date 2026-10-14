from pathlib import Path

import fitz
import pytest

from document_reader import (
    MAX_BYTES,
    MAX_PAGES,
    find_tesseract,
    read_document,
    read_path,
)

CASES = Path(__file__).resolve().parent.parent / "data" / "cases"
needs_data = pytest.mark.skipif(
    not CASES.exists(), reason="dataset not generated"
)
needs_ocr = pytest.mark.skipif(
    find_tesseract() is None, reason="Tesseract not installed"
)


@needs_data
def test_text_pdf_is_read_without_ocr():
    r = read_path(CASES / "case_01" / "id_card.pdf")
    assert r.status == "ok" and r.method == "pdf_text"
    assert r.needs_review is False
    assert "VD-000101" in r.text and "Ayesha Khan" in r.text


@needs_data
def test_all_clean_documents_in_case_01_are_ok():
    for name in ("id_card", "transcript", "degree"):
        r = read_path(CASES / "case_01" / f"{name}.pdf")
        assert r.status == "ok", name


@needs_data
@needs_ocr
def test_scanned_transcript_uses_ocr():
    r = read_path(CASES / "case_05" / "transcript.png")
    assert r.status == "ok" and r.method == "ocr"
    assert "CGPA" in r.text.upper()


@needs_data
@needs_ocr
def test_scanned_id_number_is_read():
    r = read_path(CASES / "case_05" / "id_card.png")
    assert "000105" in r.text.replace(" ", "")


@needs_data
@needs_ocr
def test_blurry_id_is_not_trusted():
    r = read_path(CASES / "case_17" / "id_card.png")
    assert r.needs_review or "VD-000117" not in r.text


def test_empty_file():
    r = read_document(b"", "a.pdf")
    assert r.status == "empty_file" and r.needs_review


def test_unsupported_extension():
    r = read_document(b"hello", "notes.txt")
    assert r.status == "unsupported_type" and r.needs_review


def test_extension_does_not_match_content():
    r = read_document(b"\x89PNG\r\n\x1a\n" + b"x" * 50, "fake.pdf")
    assert r.status == "unsupported_type"


def test_too_large_file():
    r = read_document(b"%PDF" + b"0" * MAX_BYTES, "big.pdf")
    assert r.status == "too_large" and r.needs_review


def test_corrupted_pdf():
    r = read_document(b"%PDF-1.4\nthis is not a real pdf", "bad.pdf")
    assert r.status == "corrupted" and r.needs_review


def test_corrupted_png():
    r = read_document(b"\x89PNG\r\n\x1a\n" + b"garbage", "bad.png")
    assert r.status == "corrupted" and r.needs_review


def test_blank_pdf_goes_to_review():
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    r = read_document(data, "blank.pdf")
    assert r.needs_review is True
    assert r.status in {"insufficient_text", "ocr_unavailable"}


def _text_pdf(num_pages):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text(
            (72, 90),
            f"Page {i + 1}: this page has plenty of readable sample text.",
        )
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_at_page_limit_is_ok():
    r = read_document(_text_pdf(MAX_PAGES), "limit.pdf")
    assert r.status == "ok" and r.needs_review is False
    assert r.pages == MAX_PAGES


def test_pdf_over_page_limit_goes_to_review():
    r = read_document(_text_pdf(MAX_PAGES + 1), "long.pdf")
    assert r.status == "too_many_pages"
    assert r.needs_review is True
    assert r.text == ""