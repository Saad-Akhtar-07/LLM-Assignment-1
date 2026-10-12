"""Urdu corpus Unicode normalization. Kept separate from the BPE tokenizer."""

import re
import unicodedata


_MAP = str.maketrans({
    "ي": "ی", "ى": "ی", "ك": "ک", "ه": "ہ",
    **{chr(0x660 + i): str(i) for i in range(10)},
    **{chr(0x6F0 + i): str(i) for i in range(10)},
})
_REMOVE = {0x640, 0x200B, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF}
_REMOVE.update(range(0x202A, 0x202F))
_REMOVE.update(range(0x2066, 0x206A))


def normalize(text: str) -> str:
    """Normalize Urdu letters, digits and spacing, preserving ZWNJ and line breaks.

    ZWNJ (U+200C) is preserved because it can be linguistically meaningful in
    Urdu. Do-chashmi heh (U+06BE) is distinct from gol heh (U+06C1).
    """
    # Compatibility normalization expands Arabic presentation forms commonly
    # found in older Urdu scans before the letter substitutions below.
    text = unicodedata.normalize("NFKC", text).translate(_MAP)
    text = text.translate({codepoint: None for codepoint in _REMOVE})
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
