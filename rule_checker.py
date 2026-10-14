import re
from schemas import Application, Outcome, Result

MIN_YEARS = 16
MIN_CGPA = 2.5
ID_PATTERN = re.compile(r"^VD-\d{6}$")


def _norm(name):
    return " ".join(name.lower().split()) if name else None


def check(app: Application) -> Result:
    fails, reviews = [], []
    docs = {"id_card": app.id_card, "transcript": app.transcript, "degree": app.degree}

    # R1: all three documents present
    for key, doc in docs.items():
        if doc is None:
            fails.append(f"MISSING_DOCUMENT:{key}")

    # R2: years of education
    if app.transcript is not None:
        y = app.transcript.years_of_education
        if y is None:
            reviews.append("YEARS_UNREADABLE")
        elif y < MIN_YEARS:
            fails.append("EDUCATION_BELOW_MIN")

    # R3: CGPA
    if app.transcript is not None:
        c = app.transcript.cgpa
        if c is None:
            reviews.append("CGPA_UNREADABLE")
        elif c > 4.0 or c < 0:
            reviews.append("CGPA_OUT_OF_RANGE")
        elif c < MIN_CGPA:
            fails.append("CGPA_BELOW_MIN")

    # R4: name matches across documents
    names = []
    for doc in docs.values():
        if doc is not None:
            n = _norm(doc.full_name)
            if n is None:
                reviews.append("NAME_UNREADABLE")
            else:
                names.append(n)
    if len(set(names)) > 1:
        reviews.append("NAME_MISMATCH")

    # R5: ID number
    if app.id_card is not None:
        i = app.id_card.id_number
        if i is None:
            reviews.append("ID_UNREADABLE")
        elif not ID_PATTERN.match(i):
            fails.append("ID_INVALID")

    if fails:
        outcome = Outcome.FAIL
    elif reviews:
        outcome = Outcome.NEEDS_REVIEW
    else:
        outcome = Outcome.PASS

    return Result(
        outcome=outcome,
        reasons=fails + reviews,
        review_required=bool(reviews),
    )