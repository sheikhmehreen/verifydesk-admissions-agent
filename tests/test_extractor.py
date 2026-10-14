import json

import pytest

from extractor import LLMError, MAX_CHARS, extract_fields

TRANSCRIPT = """Academic Transcript (Sample)
Student: Ayesha Khan
Degree: BS Computer Science
Institution: Sample University (FAKE)
Graduation Year: 2023
Years of Education: 16
CGPA: 3.20 / 4.00"""

GOOD = {
    "fields": {
        "full_name": "Ayesha Khan", "degree_title": "BS Computer Science",
        "years_of_education": 16, "cgpa": 3.2,
        "institution": "Sample University (FAKE)", "graduation_year": 2023,
    },
    "evidence": {"cgpa": "CGPA: 3.20 / 4.00", "full_name": "Student: Ayesha Khan"},
}


def fake(payload):
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return lambda system, user: raw


def test_good_transcript_is_ok():
    r = extract_fields("transcript", TRANSCRIPT, llm=fake(GOOD))
    assert r.status == "ok" and r.needs_review is False
    assert r.fields.cgpa == 3.2 and r.fields.years_of_education == 16
    assert r.evidence["cgpa"] == "CGPA: 3.20 / 4.00"


def test_numbers_given_as_strings_are_accepted():
    payload = {"fields": {**GOOD["fields"], "cgpa": "3.20", "years_of_education": "16"}}
    r = extract_fields("transcript", TRANSCRIPT, llm=fake(payload))
    assert r.status == "ok" and r.fields.cgpa == 3.2


def test_id_card_ignores_fields_that_do_not_belong():
    text = "National ID Card (Sample)\nName: Ayesha Khan\nID Number: VD-000101"
    payload = {"fields": {"full_name": "Ayesha Khan", "id_number": "VD-000101", "cgpa": 3.0}}
    r = extract_fields("id_card", text, llm=fake(payload))
    assert r.status == "ok"
    assert r.fields.id_number == "VD-000101" and r.fields.cgpa is None


def test_json_in_code_fence_is_parsed():
    raw = "```json\n" + json.dumps(GOOD) + "\n```"
    assert extract_fields("transcript", TRANSCRIPT, llm=fake(raw)).status == "ok"


def test_value_not_in_document_is_removed_and_flagged():
    payload = {"fields": {**GOOD["fields"], "cgpa": 3.9}}
    r = extract_fields("transcript", TRANSCRIPT, llm=fake(payload))
    assert r.status == "fields_removed" and r.needs_review is True
    assert r.fields.cgpa is None and "cgpa" in r.dropped_fields


def test_malformed_json_goes_to_review():
    r = extract_fields("transcript", TRANSCRIPT, llm=fake("this is not json"))
    assert r.status == "malformed_output" and r.needs_review is True


def test_wrong_shape_goes_to_review():
    assert extract_fields("transcript", TRANSCRIPT, llm=fake('["a"]')).status == "malformed_output"
    assert extract_fields("transcript", TRANSCRIPT, llm=fake('{"fields": "x"}')).status == "malformed_output"


def test_bad_value_type_goes_to_review():
    payload = {"fields": {**GOOD["fields"], "cgpa": "abc"}}
    r = extract_fields("transcript", TRANSCRIPT, llm=fake(payload))
    assert r.status == "malformed_output" and r.needs_review is True


def test_empty_text_does_not_call_the_ai():
    def must_not_run(system, user):
        raise AssertionError("the AI should not be called")
    r = extract_fields("transcript", "   ", llm=must_not_run)
    assert r.status == "empty_text" and r.needs_review is True


def test_too_long_text_goes_to_review():
    r = extract_fields("transcript", "a" * (MAX_CHARS + 1), llm=fake(GOOD))
    assert r.status == "text_too_long" and r.needs_review is True


def test_rate_limit_goes_to_review():
    def limited(system, user):
        raise LLMError("rate_limited", "The AI service rate limit was hit.")
    r = extract_fields("transcript", TRANSCRIPT, llm=limited)
    assert r.status == "rate_limited" and r.needs_review is True


def test_missing_api_key_goes_to_review(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = extract_fields("transcript", TRANSCRIPT)
    assert r.status == "no_api_key" and r.needs_review is True


def test_unknown_document_type_is_a_programming_error():
    with pytest.raises(KeyError):
        extract_fields("passport", TRANSCRIPT, llm=fake(GOOD))