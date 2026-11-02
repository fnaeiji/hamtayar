# Basic text cleaning

This package currently exposes only technical cleaning of already decoded TXT
and Markdown strings. Existing folders, shared contracts, apps and workflows
are unchanged. It has no new dependencies or IO.

## Usage

```python
from packages.documents.service import CLEANING_PROFILE, clean_text

original = "\ufeff# عنوان\r\nمتن\x00\r\n"
cleaned = clean_text(original)
assert cleaned == "# عنوان\nمتن\n"
assert CLEANING_PROFILE == "basic-text-v1"
```

## Fixed behavior

Rules run in this order:

1. Remove every U+0000 (NUL).
2. Remove consecutive U+FEFF (BOM) characters at the start.
3. Replace CRLF and standalone CR with LF.

NUL removal can join adjacent text: `a + NUL + b` becomes `ab`. This is an
explicit policy, not universal handling of corrupt encodings. Internal BOMs
remain. The rules also apply inside Markdown code blocks.

All other characters remain unchanged: spaces, tabs, blank lines, Markdown
trailing spaces/hard breaks, indentation, Persian ZWNJ, Arabic/Persian letters
and digits, emoji, links, HTML, and other control characters. No trim,
whitespace collapse, Unicode normalization, Hazm, language normalization,
parsing, chunking or embedding is performed. This is not an HTML sanitizer.

Empty strings are valid. Non-string inputs raise TypeError; callers must decode
bytes before calling. The function is deterministic and idempotent. It processes
the whole string in memory; ingestion should own input size limits.

## Contract boundary

The current interface is `clean_text(text: str) -> str`. Shared document/error
contracts are not implemented in this repository yet, so this change introduces
no parallel document model and does not modify packages/contracts. A future
document adapter can call this function on the text field while retaining source
identity, version, metadata and access information. Invalid Python argument
types raise TypeError; workflow/domain error mapping belongs to that future
adapter once shared errors exist.

Keep the original text separately. Cleaning can change character offsets; this
implementation does not produce a source map and cleaned offsets must not be
used as original citation offsets.

## Tests

From the repository root, in an environment with the project's dev dependencies:

```bash
python -m pytest test/unit/test_document_cleaning.py -q
python -m pytest -q
```

Tests cover rule interactions, invalid input, Markdown/Persian preservation and
idempotence over 2,801 short combinations. Existing contract tests may be skipped
because their shared models have not been implemented; this change does not
change or bypass those tests.
