import re

INTRO_MARKERS = ('конечно', 'хорошо', 'давайте', 'вот', 'варианты')
VARIANT_TITLE_RE = re.compile(r'^\s*(?:вариант\s*\d+\s*[:.)-]?|\d+\s*[.)-])\s*$', re.IGNORECASE)
VARIANT_PREFIX_RE = re.compile(r'^\s*(?:вариант\s*\d+\s*[:.)-]?|\d+\s*[.)-])\s*', re.IGNORECASE)


def strip_intro(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    while lines:
        first = lines[0].lower()
        if any(marker in first for marker in INTRO_MARKERS):
            lines.pop(0)
            continue
        break
    return '\n'.join(lines).strip() or text.strip()


def parse_reply_variants(text: str) -> list[str]:
    normalized = re.sub(r'^\s*(?:вариант\s*\d+\s*[:.)-]?|\d+\s*[.)-])\s*$', '---', text, flags=re.IGNORECASE | re.MULTILINE)
    variants: list[str] = []
    for part in normalized.split('---'):
        lines = [line.strip() for line in part.splitlines() if line.strip()]
        while lines and VARIANT_TITLE_RE.match(lines[0]):
            lines.pop(0)
        cleaned = '\n'.join(lines).strip()
        cleaned = VARIANT_PREFIX_RE.sub('', cleaned).strip()
        cleaned = strip_intro(cleaned)
        if cleaned:
            variants.append(cleaned)
    return variants
