from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Fields(BaseModel):
    full_name: Optional[str] = None
    id_number: Optional[str] = None
    degree_title: Optional[str] = None
    years_of_education: Optional[int] = None
    cgpa: Optional[float] = None
    institution: Optional[str] = None
    graduation_year: Optional[int] = None


class Application(BaseModel):
    id_card: Optional[Fields] = None
    transcript: Optional[Fields] = None
    degree: Optional[Fields] = None


class Result(BaseModel):
    outcome: Outcome
    reasons: list[str]
    review_required: bool
    rule_version: str = "v0.2"


class ReadResult(BaseModel):
    text: str = ""
    method: str = "none"  # pdf_text, ocr or none
    status: str
    needs_review: bool
    detail: str = ""  # Must not contain document text
    pages: int = 0