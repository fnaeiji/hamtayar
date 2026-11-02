"""Regression tests for the public cleaning entry point."""
from itertools import product

import pytest

from packages.documents.service import CLEANING_PROFILE, clean_text


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("", ""),
        ("سلام world", "سلام world"),
        ("a\r\nb\rc\n", "a\nb\nc\n"),
        ("\ufeff\ufeffhello", "hello"),
        ("a\ufeffb", "a\ufeffb"),
        ("a\x00b", "ab"),
        ("\x00\ufeffa\r\x00\n", "a\n"),
        ("\ufeff\x00\ufeff", ""),
        ("\r\r\n", "\n\n"),
        ("a", "a"),
        ("a\n", "a\n"),
        ("  a\t b  \n\n\n\t\n\u00a0c\n", "  a\t b  \n\n\n\t\n\u00a0c\n"),
        ("a\x0cb\x1bc\x7fd\u2028e", "a\x0cb\x1bc\x7fd\u2028e"),
    ],
)
def test_cleaning_rules(source, expected):
    assert clean_text(source) == expected


def test_persian_unicode_and_emoji_preserved():
    source = "مي\u200cروم؛ ي ك ۱۲۳ ١٢٣ e\u0301 👩\u200d💻\u200f"
    assert clean_text(source) == source


def test_markdown_structure_preserved():
    source = (
        "# عنوان\n\n- item\n  - child\n\nline  \nnext\n\n"
        '```python\n\tprint("  hi  ")\n\n\n```\n\n'
        "    indented code\n`a  b` [link](https://example.org/a)\n"
        "| a | b |\n| --- | --- |\n| x | y |\n"
        "> quote\n\n<div>HTML remains</div>\n"
    )
    assert clean_text(source) == source


def test_technical_rules_also_apply_inside_code():
    assert clean_text("```\r\na\x00\r\n```") == "```\na\n```"


def test_original_text_is_unchanged():
    source = "\ufeffa\r\n"
    assert clean_text(source) == "a\n"
    assert source == "\ufeffa\r\n"


def test_idempotence_for_2801_combinations():
    alphabet = ("a", "\x00", "\ufeff", "\r", "\n", " ", "\u200c")
    for size in range(5):
        for characters in product(alphabet, repeat=size):
            result = clean_text("".join(characters))
            assert clean_text(result) == result


@pytest.mark.parametrize("value", [None, b"text", 123, True, [], {}])
def test_non_string_input_rejected(value):
    with pytest.raises(TypeError, match="text must be str"):
        clean_text(value)


def test_cleaning_profile():
    assert CLEANING_PROFILE == "basic-text-v1"
