import os

import streamlit as st

st.set_page_config(page_title="VerifyDesk", page_icon="📄", layout="centered")

# Streamlit Community Cloud secrets are copied server-side into environment variables.
for _key in ("GROQ_API_KEY", "SUPABASE_URL", "SUPABASE_SECRET_KEY", "SAVE_RESULTS"):
    if not os.getenv(_key):
        try:
            value = st.secrets.get(_key)
            if value:
                os.environ[_key] = str(value)
        except Exception:
            pass

from database import DBError, save_application
from rule_checker import MIN_CGPA, MIN_YEARS
from workflow import process_application

SAVE_RESULTS = os.getenv("SAVE_RESULTS", "true").strip().lower() != "false"
MAX_RUNS_PER_SESSION = 10
MAX_FILE_BYTES = 5 * 1024 * 1024
SLOTS = [
    ("id_card", "ID card"),
    ("transcript", "Transcript"),
    ("degree", "Degree certificate"),
]
LABELS = dict(SLOTS)


def explain(code: str) -> str:
    kind, _, detail = code.partition(":")
    messages = {
        "MISSING_DOCUMENT": f"A required document was not uploaded: {LABELS.get(detail, detail)}.",
        "EDUCATION_BELOW_MIN": f"Years of education are below the sample minimum of {MIN_YEARS}.",
        "CGPA_BELOW_MIN": f"CGPA is below the sample minimum of {MIN_CGPA}.",
        "ID_INVALID": "The ID number is not in the expected format (VD-000000).",
        "NAME_MISMATCH": "The name differs between documents.",
        "NAME_UNREADABLE": "A name could not be read reliably.",
        "ID_UNREADABLE": "The ID number could not be read reliably.",
        "CGPA_UNREADABLE": "The CGPA could not be read reliably.",
        "YEARS_UNREADABLE": "The years of education could not be read reliably.",
        "CGPA_OUT_OF_RANGE": "The CGPA is outside the valid 0 to 4.0 range.",
    }
    if kind == "PROCESSING_ISSUE":
        return f"A processing issue needs human review ({detail})."
    return messages.get(kind, code.replace("_", " ").capitalize())


def show(pipeline, saved_id=None, save_error=None):
    result = pipeline.result
    if result.outcome.value == "PASS":
        st.success("PASS — all sample-policy checks succeeded.")
    elif result.outcome.value == "FAIL":
        st.error("FAIL — at least one sample-policy rule was not met.")
    else:
        st.warning("NEEDS REVIEW — this application could not be verified automatically.")

    if result.review_required:
        st.info("A human reviewer should check this application.")

    st.subheader("Reasons")
    if result.reasons:
        for reason in result.reasons:
            st.write(f"- {explain(reason)}")
    else:
        st.write("No problems found under the sample policy.")

    st.subheader("Document details")
    for doc_type, report in pipeline.docs.items():
        label = LABELS.get(doc_type, doc_type)
        with st.expander(f"{label} — {report.extract_status or report.read_status}"):
            st.write(f"Read method: {report.read_method}")
            if report.detail:
                st.write(report.detail)
            st.json(report.fields.model_dump(exclude_none=True))
            if report.evidence:
                st.caption("Evidence snippets found in document text")
                st.json(report.evidence)

    if saved_id:
        st.caption(f"Saved successfully. Application ID: {saved_id}")
    elif save_error:
        st.warning(f"The result could not be saved: {save_error}")
    elif not SAVE_RESULTS:
        st.caption("Demo mode: nothing was stored.")


st.title("VerifyDesk")
st.caption(
    "Synthetic admissions-document verification demo. "
    "This is not a real admissions decision."
)
if SAVE_RESULTS:
    st.warning(
        "Upload fake (synthetic) documents only. Files and results are stored in a "
        "private database. Document text is sent to an AI service (Groq) for extraction."
    )
else:
    st.warning(
        "Upload fake (synthetic) documents only. Document text is sent to an AI service "
        "(Groq) for extraction. Demo mode: nothing you upload is stored."
    )

uploads = {
    key: st.file_uploader(
        label,
        type=["pdf", "png", "jpg", "jpeg"],
        key=key,
        help="Maximum 5 MB per file.",
    )
    for key, label in SLOTS
}

if "runs" not in st.session_state:
    st.session_state.runs = 0

if st.button("Check application", type="primary"):
    files = {}
    too_large = []
    for key, upload in uploads.items():
        if upload is None:
            continue
        content = upload.getvalue()
        if len(content) > MAX_FILE_BYTES:
            too_large.append(upload.name)
        else:
            files[key] = (content, upload.name)

    if too_large:
        st.error("These files exceed the 5 MB limit: " + ", ".join(too_large))
    elif not files:
        st.error("Upload at least one document.")
    elif st.session_state.runs >= MAX_RUNS_PER_SESSION:
        st.error("Demo limit reached for this session.")
    else:
        st.session_state.runs += 1
        try:
            with st.spinner("Reading and checking documents..."):
                pipeline = process_application(files)
        except Exception:
            st.error("Processing failed. Check the app logs and configuration; no result was saved.")
        else:
            saved_id, save_error = None, None
            if SAVE_RESULTS:
                try:
                    saved_id = save_application(files, pipeline)
                except DBError as exc:
                    save_error = str(exc)
            st.session_state.last_result = (pipeline, saved_id, save_error)

if "last_result" in st.session_state:
    show(*st.session_state.last_result)
