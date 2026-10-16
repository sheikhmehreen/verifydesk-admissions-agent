# VerifyDesk — AI Admissions Document Verification Demo

VerifyDesk is a portfolio MVP that extracts fields from **synthetic admissions documents** and applies transparent, deterministic sample-policy rules. The LLM extracts candidate fields; it does **not** make the eligibility decision. Uncertain or conflicting information is routed to human review.

> **Demo only:** Do not upload real identity documents, transcripts, or other personal data. This is not a real admissions decision system.

## Live demo

**https://verifydesk-admissions-agent-ceouz44eamwdx2ftwfreea.streamlit.app/**

Synthetic documents only. The public app runs in demo mode, which skips the save step.
The first load may be slow because free apps sleep after inactivity.

## Try it

Download sample files from [`data/cases/`](data/cases) and upload all three documents from one folder:

| Folder | Expected result |
|---|---|
| case_01 | PASS |
| case_07 | FAIL (CGPA below 2.5) |
| case_15 | NEEDS_REVIEW (name mismatch) |
| case_17 | NEEDS_REVIEW (blurry ID image) |

## Workflow

1. Upload a synthetic ID card, transcript, and/or degree certificate (PDF, PNG, or JPG; up to 5 MB each).
2. Read document text with PyMuPDF, with OCR fallback where Tesseract is installed.
3. Extract structured fields using Groq and validate them with Pydantic.
4. Apply deterministic Python rules to produce `PASS`, `FAIL`, or `NEEDS_REVIEW`.
5. Display the result, reasons, extracted fields, and available evidence.
6. If saving is enabled, store application data in Supabase and the files in a **private** Storage bucket.

## Architecture

```
Streamlit upload
  -> document_reader  (PyMuPDF text; Tesseract OCR fallback; type and size checks)
  -> extractor        (Groq JSON -> Pydantic -> grounding check against the text)
  -> rule_checker     (plain Python rules; the LLM never decides the outcome)
  -> workflow guard   (any processing problem blocks PASS)
  -> result card; optional save to Supabase (Postgres + private Storage)
```

## Sample policy

- Requires an ID card, transcript, and degree certificate for a complete application.
- Requires at least 16 years of education.
- Requires a CGPA of at least 2.5 on a 4.0 scale.
- Checks that names match across the available documents.
- Expects synthetic ID numbers in the format `VD-000123`.
- Routes unreadable fields and name mismatches to human review.

These thresholds and identifiers are invented for the demo and must not be used for real admissions decisions.

## Evaluation (20 synthetic cases)

Outcome correct 20/20, review flag correct 20/20, false passes 0, uncertain cases routed to review 7/7,
field accuracy 203/203, documents with all fields correct 55/55, unexpected values 0.
These results come from a small, clean, synthetic set that was used during development.
They are not evidence of real-world accuracy.

## Run locally

Use Python 3.12+ (Python 3.14 may also work depending on installed wheels).

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env` locally with your own values. Never commit `.env` or paste secrets into issues or chat.

```
python -m pytest -q
python -m streamlit run app.py
```

## Configuration

| Variable | Purpose |
|---|---|
| GROQ_API_KEY | LLM extraction |
| SAVE_RESULTS | "false" = demo mode, nothing is saved (default "true") |
| SUPABASE_URL, SUPABASE_SECRET_KEY | only needed when saving is on |

## Supabase setup

The SQL schema is in [`supabase/schema.sql`](supabase/schema.sql). The database needs `applications`, `documents`, `extractions`, and `results`, with RLS enabled, plus a private Storage bucket named `documents`.

The app uses `SUPABASE_SECRET_KEY` only server-side. Never put it in browser-side code or a public repository. RLS is enabled without public policies by design. Do not add broad public policies just to make writes work.

## Streamlit Community Cloud deployment

1. Deploy this repository from Streamlit Community Cloud with `app.py` as the entry point. `packages.txt` installs Tesseract.
2. Add these secrets in the app settings (use real values privately; never commit them):

```
GROQ_API_KEY = "your-groq-key"
SAVE_RESULTS = "false"
```

   For a private test with saving on, also add `SUPABASE_URL` and `SUPABASE_SECRET_KEY` and set `SAVE_RESULTS = "true"`.
3. Reboot the app and test with synthetic documents only.
4. With saving on, confirm a "Saved. Application ID" line and matching rows in Supabase. In demo mode, confirm the page says "Demo mode: nothing was stored."

## Privacy and limitations

- Synthetic documents only. Do not upload real personal data.
- Document text is sent to Groq for extraction. Review Groq's current data terms.
- With saving on, files go to a private Supabase bucket. Demo mode skips the save step.
- It checks consistency, not authenticity. Forged documents are not detected.
- No login and no per-user isolation. The session cap is a demo guard, not security.
- The Supabase secret key bypasses RLS and must stay in trusted server-side secrets.
- Prompt-injection testing is not yet part of the evaluation.
- Production authentication, retention, auditing, and a human-review console are not implemented.
- The rules and thresholds are invented and must not be used for real admissions.

## Quality checks

GitHub Actions runs Python compilation and `pytest` for pushes to `main` and pull requests targeting `main`.