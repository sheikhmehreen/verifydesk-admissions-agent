from schemas import Application, Fields, Outcome
from rule_checker import check


def good():
    return Application(
        id_card=Fields(full_name="Ayesha Khan", id_number="VD-000123"),
        transcript=Fields(full_name="Ayesha Khan", cgpa=3.2, years_of_education=16),
        degree=Fields(full_name="Ayesha Khan", degree_title="BS Computer Science"),
    )


def test_clean_passes():
    assert check(good()).outcome == Outcome.PASS


def test_low_cgpa_fails():
    a = good()
    a.transcript.cgpa = 2.3
    r = check(a)
    assert r.outcome == Outcome.FAIL and "CGPA_BELOW_MIN" in r.reasons


def test_unreadable_cgpa_needs_review():
    a = good()
    a.transcript.cgpa = None
    assert check(a).outcome == Outcome.NEEDS_REVIEW


def test_name_mismatch_needs_review():
    a = good()
    a.degree.full_name = "Ayesha Khann"
    assert check(a).outcome == Outcome.NEEDS_REVIEW


def test_missing_document_fails():
    a = good()
    a.degree = None
    assert check(a).outcome == Outcome.FAIL


def test_fail_keeps_review_flag():
    a = good()
    a.transcript.cgpa = 2.3
    a.id_card.id_number = None
    r = check(a)
    assert r.outcome == Outcome.FAIL and r.review_required is True