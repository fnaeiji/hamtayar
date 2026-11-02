"""Deterministic technical cleaning of already decoded TXT/Markdown text."""

CLEANING_PROFILE = "basic-text-v1"


def clean_text(text: str) -> str:
    """Remove NUL and leading BOMs, then canonicalize CRLF/CR to LF.

    Preserve all other characters, including whitespace, Persian ZWNJ,
    Markdown hard breaks, indentation and code. These three technical rules
    apply inside code blocks too. This is not a Markdown parser or sanitizer.

    NUL removal comes first so newly adjacent CR/LF and leading BOMs are
    resolved in this pass. Cleaning the returned text again is a no-op.
    Source character offsets may change; callers must retain the original.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str; decode bytes before cleaning")
    return text.replace("\x00", "").lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
