"""زبان مشترک همتایار. همهٔ ماژول‌ها فقط از همین نقطه `import` می‌کنند.

قاعده: `contracts` به هیچ ماژول دیگری از پروژه وابسته نیست (وابستگی فقط یک‌طرفه).
"""
# Pending modules: each one must exist next to this file before its import is restored.
#   answering -> AnswerRequest, AnswerResult, AnswerStatus, Citation
#   chunks    -> Chunk, ChunkKind
#   code      -> BackendIndexRef, CodeAnalysisResult, CodeFile, RelationType,
#                Relationship, Symbol, SymbolType
#   common    -> AccessScope, Contract, EvidenceRef, Location, SourceId,
#                SourceKind, VersionId
#   documents -> DocumentMetadata, ParsedDocument, Section, Table
#   errors    -> AccessDeniedError, AccessScopeMissingError, ErrorCode, ErrorInfo,
#                HamtayarError, ProviderUnavailableError, PublicationFailedError,
#                UnsupportedFormatError
#   ingestion -> IngestionReceipt, IngestionRequest, IngestionStatus, JobStatus,
#                PublicationState
#   retrieval -> SearchHit, SearchMode, SearchRequest, SearchResponse

__all__: list[str] = []
