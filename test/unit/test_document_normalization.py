"""Real Hazm regression tests; dependency failures must fail, not skip."""
import builtins
from dataclasses import FrozenInstanceError, asdict, fields, replace
from importlib.metadata import version
import json

import pytest

from packages.documents import normalizer as adapter
from packages.documents.service import (
    NormalizationConfig, PersianNormalizer, clean_text, normalize_text,
)


def only(**options):
    flags = {field.name: False for field in fields(NormalizationConfig)}
    return NormalizationConfig(**(flags | {"enabled": True} | options))


@pytest.mark.parametrize(("option", "source", "expected"), [
    ("normalize_characters", "علي كيان", "علی کیان"),
    ("remove_diacritics", "حَذفِ اِعراب", "حذف اعراب"),
    ("correct_spacing", "سلام   دنیا", "سلام دنیا"),
    ("persian_numbers", "نسخه 123", "نسخه ۱۲۳"),
    ("persian_style", '"سلام" ...', '«سلام» …'),
    ("unicode_replacements", "﷽", "بسم الله الرحمن الرحیم"),
    ("remove_special_chars", "پیامبر ﷺ", "پیامبر "),
    ("decrease_repeated_chars", "سلامممم", "سلام"),
    ("separate_mi", "نمیدانم چه میگفت", "نمی‌دانم چه می‌گفت"),
])
def test_each_option_on_and_off_with_real_hazm(option, source, expected):
    assert normalize_text(source, only(**{option: True})) == expected
    assert normalize_text(source, only()) == source


def test_default_policy():
    assert normalize_text('عَلِي كيان 123 "سلام" ...') == 'علی کیان 123 "سلام" ...'


def test_all_options_off_is_identity():
    text = '\ufeffعَلِي ك 123\x00\r\n\tسلامممم ﷺ'
    assert normalize_text(text, only()) == text


def test_normalize_characters_can_be_disabled_independently():
    assert normalize_text('عَلِي ك 12', only(remove_diacritics=True)) == 'علي ك 12'


def test_disabled_is_exact_identity_and_does_not_load_backend(monkeypatch):
    def fail(_):
        pytest.fail('disabled normalizer loaded Hazm')
    monkeypatch.setattr(adapter, '_make_backend', fail)
    source = '\ufeff# عَلِي\r\n```\nك=123\n```\x00'
    assert normalize_text(source, NormalizationConfig(enabled=False)) == source


@pytest.mark.parametrize('text', ['', ' ', '\t\n\r\n', '  \t'])
def test_empty_or_whitespace_does_not_load_backend(text, monkeypatch):
    def fail(_):
        pytest.fail('empty content loaded Hazm')
    monkeypatch.setattr(adapter, '_make_backend', fail)
    assert normalize_text(text) == text


def test_layout_preserved_with_spacing_enabled():
    source = '  سلام   دنیا  \r\n\tمتن   فارسی\n\n\n'
    assert normalize_text(source, only(correct_spacing=True)) == '  سلام دنیا  \r\n\tمتن فارسی\n\n\n'


def test_zwnj_emoji_and_english():
    text = 'می‌روم 👩‍💻 English v1.2 https://example.org/a'
    assert normalize_text(text) == text


def test_protected_markdown_code_and_link_with_length_changes():
    source = 'عَلِي `ك=123` و [لينك](https://host/ك/123)\n```python\nك = 123\n```\nكِتاب'
    snippets = ['`ك=123`', '[لينك](https://host/ك/123)', '```python\nك = 123\n```']
    ranges = [(source.index(s), source.index(s) + len(s)) for s in snippets]
    config = NormalizationConfig(persian_numbers=True, correct_spacing=True)
    result = normalize_text(source, config, protected_ranges=ranges)
    assert result == 'علی `ك=123` و [لينك](https://host/ك/123)\n```python\nك = 123\n```\nکتاب'
    assert source.startswith('عَلِي')


def test_entire_input_protected_does_not_load_backend(monkeypatch):
    def fail(_):
        pytest.fail('protected content loaded Hazm')
    monkeypatch.setattr(adapter, '_make_backend', fail)
    text = 'ك 123'
    assert normalize_text(text, protected_ranges=[(0, len(text))]) == text


def test_adjacent_ranges_and_edges():
    assert normalize_text('يكك', protected_ranges=[(0, 1), (1, 2)]) == 'يكک'
    assert normalize_text('يكك', protected_ranges=[(2, 3)]) == 'یکك'


@pytest.mark.parametrize('ranges', [[(-1, 2)], [(0, 0)], [(2, 1)], [(0, 4)], [(1, 3), (0, 1)], [(0, 2), (1, 3)], [(0,)], ['ab']])
def test_invalid_ranges_rejected(ranges):
    with pytest.raises(ValueError):
        normalize_text('abc', protected_ranges=ranges)


@pytest.mark.parametrize('ranges', [[(True, 2)], [(0, 2.5)], [('0', 2)]])
def test_invalid_offset_types(ranges):
    with pytest.raises(TypeError):
        normalize_text('abc', protected_ranges=ranges)


def test_disabled_still_validates_ranges():
    with pytest.raises(ValueError):
        normalize_text('abc', NormalizationConfig(enabled=False), protected_ranges=[(0, 9)])


@pytest.mark.parametrize('text', [None, b'text', 1, [], {}])
def test_invalid_text(text):
    with pytest.raises(TypeError, match='text must be str'):
        normalize_text(text)


@pytest.mark.parametrize('field', [field.name for field in fields(NormalizationConfig)])
def test_config_rejects_coercion(field):
    with pytest.raises(TypeError, match='must be bool'):
        NormalizationConfig(**{field: 'false'})


def test_invalid_config_and_unknown_option():
    with pytest.raises(TypeError):
        PersianNormalizer({})
    with pytest.raises(TypeError):
        NormalizationConfig(unknown=True)


def test_frozen_config_and_json_roundtrip():
    config = NormalizationConfig(persian_numbers=True)
    assert NormalizationConfig(**json.loads(json.dumps(asdict(config)))) == config
    with pytest.raises(FrozenInstanceError):
        config.enabled = False


def test_reuse_backend_and_isolate_configurations(monkeypatch):
    original = adapter._make_backend
    calls = []
    def counting(config):
        calls.append(config)
        return original(config)
    monkeypatch.setattr(adapter, '_make_backend', counting)
    normalizer = PersianNormalizer(only(persian_numbers=True))
    assert normalizer.normalize('12') == '۱۲'
    assert normalizer.normalize('34') == '۳۴'
    assert len(calls) == 1
    assert normalize_text('12', only()) == '12'
    assert normalizer.config.persian_numbers is True


def test_missing_hazm_has_actionable_error(monkeypatch):
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == 'hazm':
            raise ModuleNotFoundError("No module named 'hazm'", name='hazm')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', missing)
    with pytest.raises(RuntimeError, match='normalization'):
        normalize_text('علي')
    assert clean_text('\ufeffa\r\n') == 'a\n'
    assert normalize_text('علي', NormalizationConfig(enabled=False)) == 'علي'


def test_upstream_dependency_failure_not_hidden(monkeypatch):
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == 'hazm':
            raise ModuleNotFoundError('broken dependency', name='nltk')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', missing)
    with pytest.raises(ModuleNotFoundError, match='broken dependency'):
        normalize_text('علي')


def test_clean_then_normalize():
    source = '\ufeffعَلِي كيان\r\n\x00نسخه 12'
    assert normalize_text(clean_text(source)) == 'علی کیان\nنسخه 12'
    assert source.startswith('\ufeff')


@pytest.mark.parametrize('source', ['عَلِي كيان', 'می‌روم', 'English 123', 'سَلام\n\nدُنيا', '👩‍💻'])
def test_default_idempotence_for_representative_prose(source):
    result = normalize_text(source)
    assert normalize_text(result) == result


def test_supported_hazm_version():
    assert version('hazm') == '0.12.1'


def test_all_options_together_with_real_hazm():
    config = NormalizationConfig(**{field.name: True for field in fields(NormalizationConfig)})
    assert normalize_text('عَلِي كيان 123 سلامممم نمیدانم', config) == 'علی کیان ۱۲۳ سلام نمی‌دانم'


def test_public_import_and_bypass_without_site_packages():
    import subprocess
    import sys
    from pathlib import Path
    result = subprocess.run(
        [sys.executable, '-S', '-c',
         'from packages.documents.service import clean_text, normalize_text, NormalizationConfig; '
         'assert clean_text("a\\r\\n") == "a\\n"; '
         'assert normalize_text("علي", NormalizationConfig(enabled=False)) == "علي"'],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
