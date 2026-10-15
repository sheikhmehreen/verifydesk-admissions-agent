from document_reader import read_document
from extractor import call_groq, extract_fields
from rule_checker import check
from schemas import Application, DocReport, Fields, Outcome, PipelineResult

DOC_TYPES = ("id_card", "transcript", "degree")


def process_application(files: dict, llm=call_groq) -> PipelineResult:
    unknown = set(files) - set(DOC_TYPES)
    if unknown:
        raise ValueError(f"Unknown document type(s): {sorted(unknown)}")

    reports = {}
    fields_by_type = {}

    for doc_type in DOC_TYPES:
        if doc_type not in files:
            continue

        data, filename = files[doc_type]
        read = read_document(data, filename)

        if read.needs_review:
            reports[doc_type] = DocReport(
                read_status=read.status,
                read_method=read.method,
                needs_review=True,
                detail=read.detail,
            )
            fields_by_type[doc_type] = Fields()
            continue

        extracted = extract_fields(doc_type, read.text, llm=llm)
        reports[doc_type] = DocReport(
            read_status=read.status,
            read_method=read.method,
            extract_status=extracted.status,
            needs_review=extracted.needs_review,
            detail=extracted.detail,
            fields=extracted.fields,
            evidence=extracted.evidence,
        )
        fields_by_type[doc_type] = extracted.fields

    application = Application(
        id_card=fields_by_type.get("id_card"),
        transcript=fields_by_type.get("transcript"),
        degree=fields_by_type.get("degree"),
    )
    result = check(application)

    issues = [
        f"{doc_type}:{report.extract_status or report.read_status}"
        for doc_type, report in reports.items()
        if report.needs_review
    ]
    if issues and result.outcome != Outcome.FAIL:
        result = result.model_copy(update={
            "outcome": Outcome.NEEDS_REVIEW,
            "review_required": True,
            "reasons": result.reasons + [
                f"PROCESSING_ISSUE:{issue}" for issue in issues
            ],
        })

    return PipelineResult(result=result, docs=reports)
