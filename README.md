# VerifyDesk — AI Admissions Document Verification Demo

VerifyDesk is a portfolio MVP that extracts fields from **synthetic admissions documents** and applies transparent, deterministic sample-policy rules. The LLM extracts candidate fields; it does **not** make the eligibility decision. Uncertain or conflicting information is routed to human review.

> **Demo only:** Do not upload real identity documents, transcripts, or other personal data. This is not a real admissions decision system.

## Workflow

1. Upload synthetic ID card, transcript, and/or degree certificate (PDF, PNG, or JPG; up to 5 MB each).
2. Read document text with PyMuPDF, with OCR fallback where Tesseract is installed.
3. Extract structured fields using Groq and validate them with Pydantic.
4. Apply deterministic Python rules to produce `PASS`, `FAIL`, or `NEEDS_REVIEW`.
5. Display the result, reasons, extracted fields, and available evidence.
6. If Supabase is configured, save application metadata, documents in a **private** Storage bucket, extracted fields/evidence, and the result.

## Sample policy

- Requires ID card, transcript, and degree certificate for a complete application.
- Requires at least 16 years of education.
- Requires CGPA of at least 2.5 on a 4.0 scale.
- Checks that names match across available documents.
- Expects synthetic ID numbers in the format `VD-000123`.
- Routes unreadable fields and name mismatches to human review.

These thresholds and identifiers are invented for the demo and must not be used for real admissions decisions.

## Run locally

Use Python 3.12+ (Python 3.14 may also work depending on installed wheels).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill `.env` locally with your own `GROQ_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SECRET_KEY`. Never commit `.env` or paste secrets into issues or chat.

```powershell
python -m pytest -q
python -m streamlit run app.py
```

## Supabase setup

The SQL schema is in [`supabase/schema.sql`](supabase/schema.sql). The database should have `applications`, `documents`, `extractions`, and `results`, with RLS enabled. A private Storage bucket named `documents` is also required.

The app uses `SUPABASE_SECRET_KEY` only server-side to write to the database and private bucket. Never put this key in browser-side code or a public repository. RLS is enabled without public access policies by design for this server-side demo. Do not add broad public policies just to make writes work.

## Streamlit Community Cloud deployment

1. Deploy this repository from Streamlit Community Cloud with `app.py` as the entry point.
2. Add these secrets in the app settings (use real values privately; never commit them):
   ```toml
   GROQ_API_KEY = "your-groq-key"
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_SECRET_KEY = "your-supabase-secret-key"
   ```
3. Reboot the app and test with synthetic documents only.
4. Confirm the result appears, a saved application ID is displayed, and matching records appear in Supabase.
5. Tesseract may need additional installation/configuration on the hosted environment for scanned files. Start the hosted smoke test with a text-based PDF.

## Security and limitations

- Use synthetic documents only. This is a demonstration, not production admissions software.
- Uploaded files are stored in private Supabase Storage when persistence is configured.
- The session run limit is a demo guard, not a security boundary.
- The Supabase secret key bypasses RLS; keep it exclusively in trusted server-side secrets.
- There is no user login or per-user record isolation. Do not expose real applicant data.
- Production-grade authentication, authorization, retention, auditing, and a human-review console are not implemented.

## Quality checks

GitHub Actions runs Python compilation and `pytest` for pushes to `main` and pull requests targeting `main`.
