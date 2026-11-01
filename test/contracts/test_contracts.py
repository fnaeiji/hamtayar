"""آزمون قراردادها: اعتبارسنجی، قاعدهٔ امنیتی دسترسی و استقلال `contracts` از بقیه."""
import ast
import pathlib

import pytest
from pydantic import ValidationError

try:
    from packages.contracts import (
        AccessScope, AnswerRequest, AnswerResult, AnswerStatus, BackendIndexRef, Chunk, ChunkKind,
        Citation, CodeAnalysisResult, ErrorCode, EvidenceRef, IngestionRequest, IngestionStatus,
        JobStatus, Location, ParsedDocument, ProviderUnavailableError, PublicationState,
        RelationType, Relationship, SearchHit, SearchMode, SearchRequest, SearchResponse,
        SourceKind, Symbol, SymbolType, UnsupportedFormatError,
    )
except ImportError as exc:  # contract modules are not implemented yet
    pytest.skip(f"contract layer not implemented: {exc}", allow_module_level=True)

SCOPE = AccessScope(subject_id="user-1", allowed_source_ids=frozenset({"doc-101"}))
EV = EvidenceRef(source_id="doc-101", version="v1", location=Location(page=3))


# ---- قواعد عمومی
def test_models_are_frozen_and_forbid_extra_fields():
    loc = Location(page=1)
    with pytest.raises(ValidationError):
        loc.page = 2  # تغییرناپذیر
    with pytest.raises(ValidationError):
        Location(page=1, unknown="x")  # فیلد اضافه ممنوع


def test_location_needs_a_field_and_valid_lines():
    with pytest.raises(ValidationError):
        Location()
    with pytest.raises(ValidationError):
        Location(file_path="a.py", start_line=10, end_line=5)


# ---- ingestion
def test_idempotency_key_and_status_separation():
    r = IngestionRequest(source_id="doc-101", version="v2", source_kind=SourceKind.DOCUMENT,
                         content_ref="padeen://documents/doc-101/v2")
    assert r.idempotency_key == "doc-101:v2"
    s = IngestionStatus(job_id="j1", source_id="doc-101", version="v2", job_status=JobStatus.RUNNING)
    assert s.publication_state is PublicationState.NOT_PUBLISHED  # پیش‌فرض: منتشر نشده


# ---- documents (نمونهٔ ساده‌شدهٔ سند)
def test_parsed_document_sample():
    doc = ParsedDocument.model_validate({
        "source_id": "doc-101", "version": "v1",
        "sections": [{"heading": "System Architecture", "text": "The system consists of...",
                      "location": {"page": 5}}],
        "metadata": {"format": "pdf", "language": "en"},
    })
    assert doc.sections[0].location.page == 5
    with pytest.raises(ValidationError):  # سند بدون بخش معتبر نیست
        ParsedDocument.model_validate({"source_id": "d", "version": "v", "sections": [],
                                       "metadata": {"format": "pdf"}})


# ---- code
def test_code_example_user_service_contains_get_user():
    sym_c = Symbol(symbol_id="c1", name="UserService", symbol_type=SymbolType.CLASS,
                   file_path="user.py", start_line=1, end_line=3)
    sym_m = Symbol(symbol_id="m1", name="get_user", symbol_type=SymbolType.METHOD,
                   file_path="user.py", start_line=2, end_line=3, signature="get_user(self, user_id)")
    rel = Relationship(from_id="c1", to_id="m1", relation=RelationType.CONTAINS)
    res = CodeAnalysisResult(source_id="repo-1", version="abc123", provider="tree_sitter",
                             symbols=[sym_c, sym_m], relationships=[rel])
    assert res.relationships[0].relation == "CONTAINS"


def test_backend_mode_may_return_only_index_ref_but_not_empty():
    ok = CodeAnalysisResult(source_id="r", version="v", provider="p",
                            backend_index=BackendIndexRef(index_id="idx-1", capabilities=["symbol_search"]))
    assert ok.backend_index
    with pytest.raises(ValidationError):
        CodeAnalysisResult(source_id="r", version="v", provider="p")


# ---- chunks
def test_chunk_keeps_link_to_source_and_version():
    c = Chunk(chunk_id="c1", source_id="doc-101", version="v1", kind=ChunkKind.DOCUMENT,
              text="hello", location=Location(page=2))
    assert c.evidence.source_id == "doc-101" and c.evidence.version == "v1"
    with pytest.raises(ValidationError):
        Chunk(chunk_id="c1", source_id="doc-101", version="v1", kind=ChunkKind.DOCUMENT,
              text="", location=Location(page=2))


# ---- retrieval + امنیت
def test_search_request_without_access_scope_is_rejected():
    """نبود محدودهٔ دسترسی نباید به جست‌وجوی بی‌محدودیت تبدیل شود."""
    with pytest.raises(ValidationError):
        SearchRequest.model_validate({"query": "token"})


def test_empty_allowed_sources_is_explicit_deny_all():
    scope = AccessScope(subject_id="u", allowed_source_ids=frozenset())
    req = SearchRequest(query="x", access_scope=scope)
    assert req.access_scope.allowed_source_ids == frozenset()
    assert req.mode is SearchMode.HYBRID and req.top_k == 10


def test_search_hit_needs_content_or_ref_and_matches_doc_sample():
    hit = SearchHit(evidence=EvidenceRef(source_id="repo-101", version="v1",
                                         location=Location(file_path="auth/token.py", start_line=20, end_line=45)),
                    symbol="validate_token", content_ref="chunk://c9", rank=1, score=0.92)
    assert SearchResponse(hits=[hit]).partial is False
    with pytest.raises(ValidationError):
        SearchHit(evidence=EV, rank=1, score=0.5)


# ---- answering
def test_answer_status_rules():
    ok = AnswerResult(status=AnswerStatus.COMPLETED, answer="Qdrant", citations=[Citation(evidence=EV)])
    assert ok.citations
    with pytest.raises(ValidationError):
        AnswerResult(status=AnswerStatus.COMPLETED, answer="بدون ارجاع")
    with pytest.raises(ValidationError):
        AnswerResult(status=AnswerStatus.NO_EVIDENCE, answer="نباید پاسخ داشته باشد")
    with pytest.raises(ValidationError):
        AnswerResult(status=AnswerStatus.FAILED)
    assert AnswerResult(status=AnswerStatus.NO_EVIDENCE).answer is None


def test_answer_request_can_have_no_evidence_but_needs_scope():
    assert AnswerRequest(question="?", access_scope=SCOPE).evidence == []
    with pytest.raises(ValidationError):
        AnswerRequest(question="?")


# ---- errors
def test_errors_convert_to_info():
    info = UnsupportedFormatError("فرمت .xyz پشتیبانی نمی‌شود").to_info()
    assert info.code is ErrorCode.UNSUPPORTED_FORMAT and info.retryable is False
    assert ProviderUnavailableError("پادین پاسخ نداد").to_info().retryable is True


# ---- JSON رفت‌وبرگشت (انتقال بین ماژول‌ها/API)
def test_json_roundtrip():
    req = SearchRequest(query="x", access_scope=SCOPE)
    assert SearchRequest.model_validate_json(req.model_dump_json()) == req


# ---- قاعدهٔ معماری: contracts به ماژول دیگری از پروژه وابسته نیست
def test_contracts_does_not_import_other_project_packages():
    root = pathlib.Path(__file__).resolve().parents[2] / "packages" / "contracts"
    for f in root.glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module]
            for m in mods:
                assert not m.startswith("packages") and not m.startswith("apps"), f"{f.name} imports {m}"
