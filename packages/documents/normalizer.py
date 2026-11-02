"""Configurable Hazm adapter for prose; no parsing, cleaning, storage or IO."""
from collections.abc import Sequence
from dataclasses import dataclass, fields
import re

NORMALIZATION_PROFILE = "hazm-fa-v1"

# Order matches Hazm 0.12.1. Public names hide upstream spelling mistakes.
_STEPS = (
    ("persian_style", "persian_style"),
    ("persian_numbers", "persian_number"),
    ("remove_diacritics", "remove_diacritics"),
    ("correct_spacing", "correct_spacing"),
    ("unicode_replacements", "unicodes_replacement"),
    ("remove_special_chars", "remove_specials_chars"),
    ("decrease_repeated_chars", "decrease_repeated_chars"),
    ("separate_mi", "seperate_mi"),
)


@dataclass(frozen=True)
class NormalizationConfig:
    """Local configuration, not a shared document contract. Strict booleans."""
    enabled: bool = True
    normalize_characters: bool = True
    remove_diacritics: bool = True
    correct_spacing: bool = False
    persian_numbers: bool = False
    persian_style: bool = False
    unicode_replacements: bool = False
    remove_special_chars: bool = False
    decrease_repeated_chars: bool = False
    separate_mi: bool = False

    def __post_init__(self) -> None:
        for field in fields(self):
            if type(getattr(self, field.name)) is not bool:
                raise TypeError(f"{field.name} must be bool")


def _make_backend(config: NormalizationConfig):
    # Lazy import: clean_text and disabled normalization do not need Hazm.
    try:
        from hazm import Normalizer
    except ModuleNotFoundError as exc:
        if exc.name != "hazm":
            raise
        raise RuntimeError('Install normalization dependencies: pip install -e ".[normalization]"') from exc
    return Normalizer(
        correct_spacing=config.correct_spacing,
        remove_diacritics=config.remove_diacritics,
        remove_specials_chars=config.remove_special_chars,
        decrease_repeated_chars=config.decrease_repeated_chars,
        persian_style=config.persian_style,
        persian_numbers=config.persian_numbers,
        unicodes_replacement=config.unicode_replacements,
        seperate_mi=config.separate_mi,
    )


class PersianNormalizer:
    """Reuse one instance per worker/config to reuse Hazm's dictionaries.

    Protected ranges are sorted, non-overlapping Python character offsets in
    this exact input string: [start, end). They are never normalized. They are
    provided by the caller/parser, not discovered by a Markdown regex here.
    """

    def __init__(self, config: NormalizationConfig | None = None) -> None:
        if config is not None and not isinstance(config, NormalizationConfig):
            raise TypeError("config must be NormalizationConfig")
        self._config = config if config is not None else NormalizationConfig()
        self._backend = None

    @property
    def config(self) -> NormalizationConfig:
        return self._config

    def normalize(self, text: str, *, protected_ranges: Sequence[tuple[int, int]] = ()) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be str; decode bytes before normalization")
        # Validate before processing, including when disabled.
        ranges = tuple(protected_ranges)
        end_before = 0
        for span in ranges:
            if not isinstance(span, (tuple, list)) or len(span) != 2:
                raise ValueError("each protected range must contain start and end")
            start, end = span
            if type(start) is not int or type(end) is not int:
                raise TypeError("protected range offsets must be integers")
            if not 0 <= start < end <= len(text) or start < end_before:
                raise ValueError("protected ranges must be sorted, non-overlapping and inside text")
            end_before = end
        if not self.config.enabled or not text:
            return text
        if not self.config.normalize_characters and not any(
            getattr(self.config, name) for name, _ in _STEPS
        ):
            return text
        parts = []
        cursor = 0
        for start, end in ranges:
            parts.append(self._normalize_prose(text[cursor:start]))
            parts.append(text[start:end])
            cursor = end
        parts.append(self._normalize_prose(text[cursor:]))
        return "".join(parts)

    def _normalize_prose(self, text: str) -> str:
        # Preserve layout and whitespace at protected-range boundaries, even
        # when Hazm's spacing rule trims or collapses whitespace internally.
        pieces = re.split(r"(\r\n|\r|\n)", text)
        for index in range(0, len(pieces), 2):
            match = re.fullmatch(r"([ \t]*)(.*?)([ \t]*)", pieces[index])
            if match:
                leading, body, trailing = match.groups()
                pieces[index] = leading + self._normalize_segment(body) + trailing
        return "".join(pieces)

    def _normalize_segment(self, text: str) -> str:
        if not text:
            return text
        if self._backend is None:
            self._backend = _make_backend(self.config)
        if self.config.normalize_characters:
            # Hazm's normalize always performs its base character translation.
            return self._backend.normalize(text)
        # Skip that implicit translation, keeping selected operations independent.
        for option, method in _STEPS:
            if getattr(self.config, option):
                text = getattr(self._backend, method)(text)
        return text


def normalize_text(
    text: str,
    config: NormalizationConfig | None = None,
    *,
    protected_ranges: Sequence[tuple[int, int]] = (),
) -> str:
    """Convenience for one call. For batches, reuse PersianNormalizer instead."""
    return PersianNormalizer(config).normalize(text, protected_ranges=protected_ranges)
