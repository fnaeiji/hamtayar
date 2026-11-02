# Document text preparation

This package exposes technical cleaning and optional configurable Persian
normalization. Cleaning accepts raw TXT/Markdown; normalization operates on
prose with caller-supplied protected ranges. Shared contracts, apps and
workflows are unchanged. Cleaning remains dependency-free.

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
and digits, emoji, links, HTML, and other control characters. The cleaning function performs no trim,
whitespace collapse, Unicode normalization, Hazm, language normalization,
parsing, chunking or embedding. This is not an HTML sanitizer.

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


## Configurable Persian normalization

Install the optional extra with the existing development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,normalization]"
.\.venv\Scripts\python.exe -m pytest -q -rs
```

Hazm is pinned to **0.12.1**, tested with Python 3.12.14 on Linux. Windows was
not executed here. Normalization tests require the extra and fail if it is absent;
they do not silently skip integration with Hazm. Hazm brings transitive dependencies;
this is not a complete dependency lock. No pretrained model download or service
is needed for these normalizer operations; dictionary options use bundled data.

```python
from packages.documents.service import (
    clean_text, normalize_text, NormalizationConfig, PersianNormalizer,
)

config = NormalizationConfig(persian_numbers=True, separate_mi=True)
original = "عَلِي كيان 123 نمیدانم"
assert normalize_text(original, config) == "علی کیان ۱۲۳ نمی‌دانم"

# Reuse an instance across documents in one worker to avoid reloading dictionaries.
normalizer = PersianNormalizer(config)
result = normalizer.normalize(clean_text(original))

# Bypass is exact: no Hazm import, no cleaning, and no base character conversion.
assert normalize_text(original, NormalizationConfig(enabled=False)) == original
```

### Options and defaults

`NormalizationConfig` is an immutable local dataclass, not a shared document
contract. Every option requires a real boolean: strings such as `"false"` and
integers are rejected, as are unknown fields. Load a JSON object using
`NormalizationConfig(**settings)`; export with `dataclasses.asdict(config)`.

| Option | Default | Meaning |
|---|---|---|
| enabled | true | Entire normalization stage on/off |
| normalize_characters | true | Hazm base character mapping, including Arabic ي/ك to Persian ی/ک |
| remove_diacritics | true | Remove Arabic/Persian vowel marks |
| correct_spacing | false | Hazm spacing corrections inside prose lines |
| persian_numbers | false | Convert supported digits to Persian digits |
| persian_style | false | Persian punctuation/quote style |
| unicode_replacements | false | Hazm replacements/expansions such as ligatures |
| remove_special_chars | false | Remove Hazm's designated special characters |
| decrease_repeated_chars | false | Reduce repeated letters using Hazm rules |
| separate_mi | false | Correct supported verb prefixes using ZWNJ |

The adapter maps the public names to Hazm's `seperate_mi`,
`unicodes_replacement` and `remove_specials_chars`. Base character mapping in
Hazm normally runs even if all constructor flags are false. The adapter explicitly
bypasses that mapping when normalize_characters is false, and all operations off
is an exact identity operation. Flags control operations, not a guarantee that
other enabled rules cannot also alter the same character.

The adapter preserves CRLF/CR/LF separators, blank lines, and leading/trailing
spaces and tabs of each prose segment. Thus spacing correction deliberately
operates inside lines and does not collapse layout as raw Hazm can. Run cleaning
first if canonical LF is needed. Normalization never calls cleaning implicitly.

### Protecting code, links and other literal content

This is **not a Markdown parser**. Do not normalize an entire Markdown document
without protecting literal content or extracting prose first. The caller/parser
supplies sorted, non-overlapping `(start, end)` character ranges. Offsets are
zero-based, end-exclusive Python string offsets in the exact normalization input,
not bytes, UTF-16 units or offsets before cleaning.

```python
text = "علي `ك=123`"
start = text.index("`")
result = normalize_text(text, protected_ranges=[(start, len(text))])
assert result == "علی `ك=123`"
```

Protected substrings are copied exactly; each unprotected segment is normalized
independently, so linguistic context does not cross a protected range. Tests
include fenced code, inline code and an entire Markdown link protected explicitly,
including cases where removing preceding diacritics changes output offsets.
Automatic Markdown range detection belongs to a future parser integration.

### Lifecycle and limitations

`normalizer.py` contains the Hazm adapter, so third-party objects do not appear in
the public API. Importing service.py, using clean_text, and disabling normalization
work without Hazm installed. Backend construction is lazy and reused per instance;
use one instance per worker, not a shared mutable global normalizer. Empty or fully
protected content does not initialize Hazm. No logging, database, workflow or
permission handling is added here.

Use `NORMALIZATION_PROFILE` (`hazm-fa-v1`), the **full config**, and installed Hazm
version together to record processing settings; the profile name alone does not
identify a configuration. Original text/metadata and source mapping remain caller
responsibilities. No offset map, automatic language detection, stemming, stop-word
removal, chunking or embedding is included. Arbitrary Hazm option combinations are
not promised to be universally idempotent; representative default cases are tested.

Dependency absence raises an actionable RuntimeError; invalid argument/config
values raise TypeError/ValueError. Errors from broken upstream dependencies are
not swallowed. The future workflow adapter must map these to shared domain errors
when those contracts exist.

Upstream reference: https://github.com/roshan-research/hazm/blob/v0.12.1/hazm/normalizer.py
