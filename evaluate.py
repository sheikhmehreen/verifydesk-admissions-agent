import csv
import json
import time
from collections import Counter
from pathlib import Path

from extractor import call_groq
from workflow import process_application

DATA = Path("data")
EVAL_DELAY = 4  # seconds between AI calls
FIELD_COLS = [
    "full_name",
    "id_number",
    "degree_title",
    "years_of_education",
    "cgpa",
    "institution",
    "graduation_year",
]


def load_csv(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def norm(s):
    return " ".join(str(s).lower().split())


def same(name, expected, got):
    if got is None:
        return False

    try:
        if name == "cgpa":
            return abs(float(expected) - float(got)) < 0.005
        if name in ("years_of_education", "graduation_year"):
            return int(float(expected)) == int(got)
        return norm(expected) == norm(got)
    except (ValueError, TypeError):
        return False


def paced_llm(system, user):
    time.sleep(EVAL_DELAY)
    return call_groq(system, user)


def main():
    doc_rows = load_csv("labels_docs.csv")
    case_rows = load_csv("labels_cases.csv")

    docs_by_case = {}
    for row in doc_rows:
        docs_by_case.setdefault(int(row["case_id"]), []).append(row)

    c = Counter()
    statuses = Counter()
    latencies = []
    per_case = []
    field_mismatches = []

    for cr in case_rows:
        cid = int(cr["case_id"])
        rows = docs_by_case.get(cid, [])
        files = {}

        for row in rows:
            path = DATA / "cases" / f"case_{cid:02d}" / row["file"]
            files[row["doc_type"]] = (path.read_bytes(), path.name)

        t0 = time.time()
        out = process_application(files, llm=paced_llm)
        latencies.append(time.time() - t0)
        got = out.result

        exp_outcome = cr["expected_outcome"]
        exp_review = cr["expected_review_required"] == "True"

        outcome_ok = got.outcome.value == exp_outcome
        review_ok = got.review_required == exp_review

        c["cases"] += 1
        c["outcome_ok"] += outcome_ok
        c["review_ok"] += review_ok

        if exp_outcome != "PASS" and got.outcome.value == "PASS":
            c["false_passes"] += 1

        if exp_outcome == "NEEDS_REVIEW":
            c["uncertain_total"] += 1
            c["uncertain_routed"] += got.outcome.value == "NEEDS_REVIEW"

        for row in rows:
            report = out.docs[row["doc_type"]]
            statuses[report.extract_status or report.read_status] += 1

            if row["readable"] != "yes":
                continue

            c["readable_docs"] += 1
            doc_all_ok = True

            for col in FIELD_COLS:
                expected = row.get(col, "")
                actual = getattr(report.fields, col)

                if expected != "":
                    c["expected_fields"] += 1

                    if same(col, expected, actual):
                        c["correct_fields"] += 1
                    else:
                        doc_all_ok = False
                        field_mismatches.append({
                            "case_id": cid,
                            "doc_type": row["doc_type"],
                            "field": col,
                            "expected": expected,
                            "got": actual,
                        })

                elif actual is not None:
                    c["unexpected_values"] += 1

            c["docs_all_correct"] += doc_all_ok

        flag = "ok" if outcome_ok and review_ok else "MISMATCH"
        print(
            f"case {cid:02d}: expected {exp_outcome:12} "
            f"got {got.outcome.value:12} "
            f"review {exp_review}/{got.review_required}  {flag}"
        )

        per_case.append({
            "case_id": cid,
            "expected_outcome": exp_outcome,
            "got_outcome": got.outcome.value,
            "expected_review": exp_review,
            "got_review": got.review_required,
            "reasons": got.reasons,
            "doc_statuses": {
                doc_type: (doc.extract_status or doc.read_status)
                for doc_type, doc in out.docs.items()
            },
        })

    summary = {
        "cases": c["cases"],
        "outcome_correct": f'{c["outcome_ok"]}/{c["cases"]}',
        "review_flag_correct": f'{c["review_ok"]}/{c["cases"]}',
        "false_passes": c["false_passes"],
        "uncertain_cases_routed_to_review": (
            f'{c["uncertain_routed"]}/{c["uncertain_total"]}'
        ),
        "field_accuracy": f'{c["correct_fields"]}/{c["expected_fields"]}',
        "docs_with_all_fields_correct": (
            f'{c["docs_all_correct"]}/{c["readable_docs"]}'
        ),
        "unexpected_values_extracted": c["unexpected_values"],
        "document_statuses": dict(statuses),
        "avg_seconds_per_case_incl_pacing": (
            round(sum(latencies) / len(latencies), 1) if latencies else 0
        ),
    }

    print("\n=== SUMMARY (20-case test set; not proof of real-world reliability) ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

    print(f"\nField mismatches: {len(field_mismatches)}")
    for mismatch in field_mismatches:
        print(
            f'Case {mismatch["case_id"]:02d} | '
            f'{mismatch["doc_type"]} | {mismatch["field"]} | '
            f'expected={mismatch["expected"]!r} | '
            f'got={mismatch["got"]!r}'
        )

    with open(DATA / "eval_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "summary": summary,
            "cases": per_case,
            "field_mismatches": field_mismatches,
        }, f, indent=2)


if __name__ == "__main__":
    main()