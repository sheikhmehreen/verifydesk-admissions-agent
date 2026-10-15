import json
from pathlib import Path

import pytest

from schemas import Outcome
from workflow import process_application

CASES = Path(__file__).resolve().parent.parent / "data" / "cases"
pytestmark = pytest.mark.skipif(not CASES.exists(), reason="dataset not generated")


def files_for(case, skip=()):
    out = {}
    for doc in ("id_card", "transcript", "degree"):
        if doc in skip:
            continue
        p = CASES / case / f"{doc}.pdf"
        out[doc] = (p.read_bytes(), p.name)
    return out


def canned(per_type):
    def llm(system, user):
        doc_type = user.split("\n", 1)[0].replace("Document type: ", "").strip()
        return per_type[doc_type]
    return llm


INST = "Sample University (FAKE)"


def person(name, idn, cgpa):
    return {
        "id_card": json.dumps({"fields": {"full_name": name, "id_number": idn}}),
        "transcript": json.dumps({"fields": {
            "full_name": name, "degree_title": "BS Computer Science",
            "years_of_education": 16, "cgpa": cgpa, "institution": INST}}),
        "degree": json.dumps({"fields": {
            "full_name": name, "degree_title": "BS Computer Science",
            "institution": INST}}),
    }


CASE_01 = person("Ayesha Khan", "VD-000101", 3.2)
CASE_07 = person("Zara Iqbal", "VD-000107", 2.3)


def test_clean_application_passes():
    out = process_application(files_for("case_01"), llm=canned(CASE_01))
    assert out.result.outcome == Outcome.PASS
    assert out.result.review_required is False


def test_missing_document_fails():
    out = process_application(files_for("case_01", skip=("degree",)), llm=canned(CASE_01))
    assert out.result.outcome == Outcome.FAIL
    assert "MISSING_DOCUMENT:degree" in out.result.reasons
    assert out.result.review_required is False


def test_malformed_ai_response_goes_to_review():
    per_type = {**CASE_01, "transcript": "this is not json"}
    out = process_application(files_for("case_01"), llm=canned(per_type))
    assert out.result.outcome == Outcome.NEEDS_REVIEW
    assert out.result.review_required is True
    assert "PROCESSING_ISSUE:transcript:malformed_output" in out.result.reasons


def test_removed_value_blocks_a_pass():
    # degree_title is not used by any rule, but a made-up value must still stop a PASS
    per_type = {**CASE_01, "degree": json.dumps({"fields": {
        "full_name": "Ayesha Khan", "degree_title": "MBA Finance", "institution": INST}})}
    out = process_application(files_for("case_01"), llm=canned(per_type))
    assert out.result.outcome == Outcome.NEEDS_REVIEW
    assert "PROCESSING_ISSUE:degree:fields_removed" in out.result.reasons


def test_unreadable_file_goes_to_review():
    files = files_for("case_01")
    files["id_card"] = (b"", "id_card.pdf")
    out = process_application(files, llm=canned(CASE_01))
    assert out.result.outcome == Outcome.NEEDS_REVIEW
    assert out.result.review_required is True


def test_fail_with_unreadable_document_keeps_fail_and_review_flag():
    files = files_for("case_07")
    files["degree"] = (b"%PDF-1.4\nnot a real pdf", "degree.pdf")
    out = process_application(files, llm=canned(CASE_07))
    assert out.result.outcome == Outcome.FAIL
    assert "CGPA_BELOW_MIN" in out.result.reasons
    assert out.result.review_required is True


def test_unknown_document_type_is_rejected():
    with pytest.raises(ValueError):
        process_application({"passport": (b"x", "x.pdf")})