import pytest

import database
from database import DBError, save_application
from schemas import DocReport, Fields, Outcome, PipelineResult, Result


class FakeResp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body if body is not None else {}

    def json(self):
        return self._body


def pipeline_for(doc_types):
    docs = {
        doc_type: DocReport(
            read_status="ok",
            read_method="pdf_text",
            extract_status="ok",
            needs_review=False,
            fields=Fields(full_name="Ayesha Khan"),
        )
        for doc_type in doc_types
    }
    result = Result(outcome=Outcome.PASS, reasons=[], review_required=False)
    return PipelineResult(result=result, docs=docs)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-key")


def test_save_application_writes_every_table(monkeypatch, env):
    calls = []
    ids = iter(["app-id", "doc-1", "extract-1", "doc-2", "extract-2", "result-1"])

    def fake_post(url, headers=None, json=None, data=None, timeout=None):
        calls.append((url, json, data))
        if "/storage/" in url:
            return FakeResp(200)
        return FakeResp(201, [{"id": next(ids)}])

    monkeypatch.setattr(database.requests, "post", fake_post)
    files = {"id_card": (b"x", "id.pdf"), "transcript": (b"y", "t.png")}
    app_id = save_application(files, pipeline_for(files))

    assert app_id == "app-id"
    tables = [u.rsplit("/", 1)[-1] for u, _, _ in calls if "/rest/v1/" in u]
    assert tables == [
        "applications", "documents", "extractions",
        "documents", "extractions", "results",
    ]
    assert sum("/storage/" in u for u, _, _ in calls) == 2


def test_supabase_error_raises_dberror(monkeypatch, env):
    monkeypatch.setattr(
        database.requests,
        "post",
        lambda *args, **kwargs: FakeResp(401),
    )
    files = {"id_card": (b"x", "id.pdf")}
    with pytest.raises(DBError):
        save_application(files, pipeline_for(files))


def test_missing_configuration_raises_dberror(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    files = {"id_card": (b"x", "id.pdf")}
    with pytest.raises(DBError):
        save_application(files, pipeline_for(files))
