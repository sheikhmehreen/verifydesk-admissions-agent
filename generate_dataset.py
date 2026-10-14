import csv
import random
from pathlib import Path

import fitz
from PIL import Image, ImageFilter

from rule_checker import check
from schemas import Application, Fields

OUT = Path("data/cases")
INST = "Sample University (FAKE)"
random.seed(7)

# Each case states its expected result by hand:
#   want    = expected outcome
#   reasons = expected reason codes (order does not matter)
#   review  = expected review_required flag
CASES = [
    dict(id=1, name="Ayesha Khan", idn="VD-000101", cgpa=3.2, years=16,
         want="PASS", reasons=[], review=False),
    dict(id=2, name="Bilal Ahmed", idn="VD-000102", cgpa=3.8, years=16,
         want="PASS", reasons=[], review=False),
    dict(id=3, name="Sana Malik", idn="VD-000103", cgpa=2.5, years=16,
         want="PASS", reasons=[], review=False),
    dict(id=4, name="Hamza Raza", idn="VD-000104", cgpa=3.0, years=17,
         want="PASS", reasons=[], review=False),
    dict(id=5, name="Fatima Noor", idn="VD-000105", cgpa=3.4, years=16,
         want="PASS", reasons=[], review=False,
         id_mode="scan", tr_mode="scan", deg_mode="scan"),
    dict(id=6, name="Usman Tariq", idn="VD-000106", cgpa=2.9, years=16,
         want="PASS", reasons=[], review=False, tr_mode="scan"),
    dict(id=7, name="Zara Iqbal", idn="VD-000107", cgpa=2.3, years=16,
         want="FAIL", reasons=["CGPA_BELOW_MIN"], review=False),
    dict(id=8, name="Omar Farooq", idn="VD-000108", cgpa=2.49, years=16,
         want="FAIL", reasons=["CGPA_BELOW_MIN"], review=False),
    dict(id=9, name="Hina Shah", idn="VD-000109", cgpa=3.0, years=14,
         want="FAIL", reasons=["EDUCATION_BELOW_MIN"], review=False),
    dict(id=10, name="Ali Hassan", idn="12345", cgpa=3.1, years=16,
         want="FAIL", reasons=["ID_INVALID"], review=False),
    dict(id=11, name="Maryam Aslam", idn="VD-000111", cgpa=3.3, years=16,
         want="FAIL", reasons=["MISSING_DOCUMENT:degree"], review=False,
         deg_mode="missing"),
    dict(id=12, name="Danish Butt", idn="VD-000112", cgpa=3.0, years=16,
         want="FAIL", reasons=["MISSING_DOCUMENT:id_card"], review=False,
         id_mode="missing"),
    dict(id=13, name="Iqra Saeed", idn="VD-000113", cgpa=3.0, years=16,
         want="NEEDS_REVIEW", reasons=["CGPA_UNREADABLE"], review=True,
         omit={"cgpa"}),
    dict(id=14, name="Kamran Ali", idn="VD-000114", cgpa=3.0, years=16,
         want="NEEDS_REVIEW", reasons=["YEARS_UNREADABLE"], review=True,
         omit={"years"}),
    dict(id=15, name="Nimra Javed", idn="VD-000115", cgpa=3.1, years=16,
         want="NEEDS_REVIEW", reasons=["NAME_MISMATCH"], review=True,
         deg_name="Nimra Javaid"),
    dict(id=16, name="Saad Mehmood", idn="VD-000116", cgpa=3.1, years=16,
         want="NEEDS_REVIEW", reasons=["NAME_MISMATCH"], review=True,
         deg_name="S. Mehmood"),
    dict(id=17, name="Rabia Anwar", idn="VD-000117", cgpa=3.2, years=16,
         want="NEEDS_REVIEW", reasons=["NAME_UNREADABLE", "ID_UNREADABLE"],
         review=True, id_mode="blur"),
    dict(id=18, name="Talha Yousaf", idn="VD-000118", cgpa=3.2, years=16,
         want="NEEDS_REVIEW",
         reasons=["YEARS_UNREADABLE", "CGPA_UNREADABLE", "NAME_UNREADABLE"],
         review=True, tr_mode="blur"),
    dict(id=19, name="Mehwish Ali", idn="VD-000119", cgpa=2.3, years=16,
         want="FAIL",
         reasons=["CGPA_BELOW_MIN", "NAME_UNREADABLE", "ID_UNREADABLE"],
         review=True, id_mode="blur"),
    dict(id=20, name="Adnan Sheikh", idn="VD-000120", cgpa=4.5, years=16,
         want="NEEDS_REVIEW", reasons=["CGPA_OUT_OF_RANGE"], review=True),
]


def render_pdf(path, title, lines):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 90), title, fontsize=20)
    y = 140
    for line in lines:
        page.insert_text((72, y), line, fontsize=13)
        y += 26
    page.insert_text((72, 760), "SYNTHETIC SAMPLE - NOT A REAL DOCUMENT", fontsize=9)
    doc.save(str(path))
    doc.close()


def to_image(pdf_path, png_path, mode):
    d = fitz.open(str(pdf_path))
    d[0].get_pixmap(matrix=fitz.Matrix(2, 2)).save(str(png_path))
    d.close()
    img = Image.open(png_path).convert("L")
    if mode == "scan":
        img = img.rotate(1.5, expand=True, fillcolor=255).filter(ImageFilter.GaussianBlur(0.8))
    elif mode == "blur":
        img = img.filter(ImageFilter.GaussianBlur(9))
    img.save(png_path)
    pdf_path.unlink()


def build_doc(folder, doc_type, mode, title, lines):
    if mode == "missing":
        return None
    pdf = folder / f"{doc_type}.pdf"
    render_pdf(pdf, title, lines)
    if mode == "pdf":
        return pdf.name
    png = folder / f"{doc_type}.png"
    to_image(pdf, png, mode)
    return png.name


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    doc_rows, case_rows, errors = [], [], []

    for c in CASES:
        folder = OUT / f"case_{c['id']:02d}"
        folder.mkdir(exist_ok=True)
        omit = c.get("omit", set())
        name = c["name"]
        deg_name = c.get("deg_name", name)
        year = random.randint(2019, 2024)

        true_fields = {
            "id_card": Fields(full_name=name, id_number=c["idn"]),
            "transcript": Fields(
                full_name=name, degree_title="BS Computer Science",
                institution=INST, graduation_year=year,
                years_of_education=None if "years" in omit else c["years"],
                cgpa=None if "cgpa" in omit else c["cgpa"],
            ),
            "degree": Fields(
                full_name=deg_name, degree_title="BS Computer Science",
                institution=INST,
            ),
        }

        tr_lines = [f"Student: {name}", "Degree: BS Computer Science",
                    f"Institution: {INST}", f"Graduation Year: {year}"]
        if "years" not in omit:
            tr_lines.append(f"Years of Education: {c['years']}")
        if "cgpa" not in omit:
            tr_lines.append(f"CGPA: {c['cgpa']:.2f} / 4.00")

        specs = {
            "id_card": (c.get("id_mode", "pdf"), "National ID Card (Sample)",
                        [f"Name: {name}", f"ID Number: {c['idn']}"]),
            "transcript": (c.get("tr_mode", "pdf"), "Academic Transcript (Sample)", tr_lines),
            "degree": (c.get("deg_mode", "pdf"), "Degree Certificate (Sample)",
                       [f"This certifies that {deg_name}",
                        "has been awarded the degree of BS Computer Science",
                        INST]),
        }

        app_fields = {}
        for doc_type, (mode, title, lines) in specs.items():
            fname = build_doc(folder, doc_type, mode, title, lines)
            if mode == "missing":
                app_fields[doc_type] = None
                continue
            readable = mode != "blur"
            shown = true_fields[doc_type] if readable else Fields()
            app_fields[doc_type] = shown
            row = {"case_id": c["id"], "doc_type": doc_type, "file": fname,
                   "readable": "yes" if readable else "no"}
            row.update({k: "" if v is None else v for k, v in shown.model_dump().items()})
            doc_rows.append(row)

        app = Application(id_card=app_fields["id_card"],
                          transcript=app_fields["transcript"],
                          degree=app_fields["degree"])
        res = check(app)

        # Compare the hand-written expectations with what the rule checker returns
        problems = []
        if res.outcome.value != c["want"]:
            problems.append(f"outcome expected {c['want']}, got {res.outcome.value}")
        if sorted(res.reasons) != sorted(c["reasons"]):
            problems.append(f"reasons expected {sorted(c['reasons'])}, got {sorted(res.reasons)}")
        if res.review_required != c["review"]:
            problems.append(f"review_required expected {c['review']}, got {res.review_required}")
        if problems:
            errors.append(f"case {c['id']}: " + "; ".join(problems))

        case_rows.append({"case_id": c["id"], "expected_outcome": c["want"],
                          "expected_reasons": "|".join(c["reasons"]),
                          "expected_review_required": c["review"]})

    if errors:
        raise AssertionError("Expected results do not match rule_checker:\n" + "\n".join(errors))

    with open(OUT.parent / "labels_docs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(doc_rows[0].keys()))
        w.writeheader()
        w.writerows(doc_rows)
    with open(OUT.parent / "labels_cases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(case_rows[0].keys()))
        w.writeheader()
        w.writerows(case_rows)
    print(f"{len(CASES)} cases OK, {len(doc_rows)} documents written")


if __name__ == "__main__":
    main()