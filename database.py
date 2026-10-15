import os
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from schemas import PipelineResult

load_dotenv()

BUCKET = "documents"
TIMEOUT = 20
_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class DBError(Exception):
    """Safe, user-displayable persistence error."""


def _cfg():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise DBError("Supabase is not configured.")
    return url.rstrip("/"), key


def _headers(key, extra=None):
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    headers.update(extra or {})
    return headers


def _post(table, row):
    url, key = _cfg()
    headers = _headers(key, {
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    })
    try:
        response = requests.post(
            f"{url}/rest/v1/{table}",
            headers=headers,
            json=row,
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        raise DBError("Could not reach Supabase.") from None
    if response.status_code not in (200, 201):
        raise DBError(f"Supabase could not save a record (HTTP {response.status_code}).")
    try:
        return response.json()[0]
    except (ValueError, IndexError, KeyError, TypeError):
        raise DBError("Supabase returned an unexpected response.") from None


def _upload(path, data, content_type):
    url, key = _cfg()
    encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
    headers = _headers(key, {
        "Content-Type": content_type,
        "x-upsert": "false",
    })
    try:
        response = requests.post(
            f"{url}/storage/v1/object/{BUCKET}/{encoded_path}",
            headers=headers,
            data=data,
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        raise DBError("Could not reach Supabase Storage.") from None
    if response.status_code not in (200, 201):
        raise DBError(f"Supabase Storage could not save a file (HTTP {response.status_code}).")


def save_application(files: dict, pipeline: PipelineResult) -> str:
    """Save metadata and files; returns the application UUID."""
    app_row = _post("applications", {
        "outcome": pipeline.result.outcome.value,
        "review_required": pipeline.result.review_required,
    })
    app_id = str(app_row["id"])
    uploaded_paths = []

    try:
        for doc_type, (data, filename) in files.items():
            if doc_type not in pipeline.docs:
                raise DBError("A document report is missing.")
            ext = Path(filename).suffix.lower()
            if ext not in _CONTENT_TYPES:
                raise DBError("Unsupported file type.")
            path = f"{app_id}/{doc_type}{ext}"
            _upload(path, data, _CONTENT_TYPES[ext])
            uploaded_paths.append(path)

            report = pipeline.docs[doc_type]
            doc_row = _post("documents", {
                "application_id": app_id,
                "doc_type": doc_type,
                "file_path": path,
                "read_status": report.read_status,
                "extract_status": report.extract_status,
                "needs_review": report.needs_review,
            })
            _post("extractions", {
                "document_id": doc_row["id"],
                "fields": report.fields.model_dump(),
                "evidence": report.evidence,
                "detail": report.detail,
            })

        result = pipeline.result
        _post("results", {
            "application_id": app_id,
            "outcome": result.outcome.value,
            "reasons": result.reasons,
            "review_required": result.review_required,
            "rule_version": result.rule_version,
        })
    except DBError:
        # Best-effort cleanup of uploaded objects. Related DB rows cascade
        # when the application row is deleted (see supabase/schema.sql).
        url, key = _cfg()
        headers = _headers(key)
        for path in uploaded_paths:
            try:
                requests.delete(
                    f"{url}/storage/v1/object/{BUCKET}/"
                    + "/".join(quote(part, safe="") for part in path.split("/")),
                    headers=headers,
                    timeout=TIMEOUT,
                )
            except requests.RequestException:
                pass
        try:
            requests.delete(
                f"{url}/rest/v1/applications",
                params={"id": f"eq.{app_id}"},
                headers=headers,
                timeout=TIMEOUT,
            )
        except requests.RequestException:
            pass
        raise

    return app_id
