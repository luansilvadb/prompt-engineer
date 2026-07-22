"""Sanitização Unicode para APIs que não aceitam caracteres não-ASCII.

Extraído de src/signatures.py para quebrar dependência circular config ↔ signatures.
"""

_UNICODE_REPLACEMENTS = {
    '\u2014': '--',    # em dash
    '\u2013': '-',     # en dash
    '\u2018': "'",     # left single quote
    '\u2019': "'",     # right single quote
    '\u201c': '"',     # left double quote
    '\u201d': '"',     # right double quote
    '\u2026': '...',   # ellipsis
    '\u00a0': ' ',     # non-breaking space
    '\u00e1': 'a',     # á
    '\u00e9': 'e',     # é
    '\u00ed': 'i',     # í
    '\u00f3': 'o',     # ó
    '\u00fa': 'u',     # ú
    '\u00e0': 'a',     # à
    '\u00e2': 'a',     # â
    '\u00ea': 'e',     # ê
    '\u00f4': 'o',     # ô
    '\u00e3': 'a',     # ã
    '\u00f5': 'o',     # õ
    '\u00e7': 'c',     # ç
    '\u00c1': 'A',     # Á
    '\u00c9': 'E',     # É
    '\u00cd': 'I',     # Í
    '\u00d3': 'O',     # Ó
    '\u00da': 'U',     # Ú
    '\u00c0': 'A',     # À
    '\u00c2': 'A',     # Â
    '\u00ca': 'E',     # Ê
    '\u00d4': 'O',     # Ô
    '\u00c3': 'A',     # Ã
    '\u00d5': 'O',     # Õ
    '\u00c7': 'C',     # Ç
    '\u00ba': 'o',     # º
    '\u00aa': 'a',     # ª
}


def _sanitize_unicode_for_api(text: str) -> str:
    """Substitui caracteres Unicode problemáticos por equivalentes ASCII.

    APIs como Zhipu/Zai rejeitam caracteres não-ASCII em certos endpoints
    com erro 'ascii' codec can't encode character. Esta função garante que
    o texto passado para a API seja seguro.
    """
    if not text:
        return text
    for unicode_char, ascii_replacement in _UNICODE_REPLACEMENTS.items():
        text = text.replace(unicode_char, ascii_replacement)
    # Fallback: remove qualquer caractere não-ASCII remanescente
    return text.encode('ascii', errors='replace').decode('ascii')
