# FILE: northstar/backend/app/utils/chunk.py
from __future__ import annotations
import re
from typing import Callable, Iterable, List, Tuple, Optional

# -------------------------------
# Public, backward-compatible API
# -------------------------------

def simple_chunks(text: str, max_len: int = 1000, overlap: int = 100) -> Iterable[str]:
    """
    Backward-compatible fallback: character-based window with overlap.
    Kept for compatibility with any existing ingestion code.
    """
    i, n = 0, len(text)
    while i < n:
        j = min(i + max_len, n)
        yield text[i:j]
        i = j - overlap if j < n else j


# -------------------------------
# Recommended, production helpers
# -------------------------------

Sentence = str
Section = Tuple[str, int, int]  # (section_title, start_idx, end_idx)

_HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.*)$")
_CODEBLOCK_RE = re.compile(r"(?s)```.*?```")
_SENTENCE_RE = re.compile(
    r"""
    (?<=\S)          # preceding non-space
    (?:              # common sentence terminators
      [.!?]          # ., !, or ?
      (?:["')\]]+)?  # optional closing quotes/brackets
    )
    \s+              # whitespace after terminator
    """,
    re.VERBOSE,
)

def _split_markdown_sections(text: str) -> List[Section]:
    """
    Returns a list of sections delimited by Markdown headings (#..######).
    Each tuple: (title, start, end) where [start:end] bounds the section text.
    """
    sections: List[Section] = []
    last_pos = 0
    last_title = "Document"
    for m in _HEADING_RE.finditer(text):
        if m.start() > last_pos:
            sections.append((last_title, last_pos, m.start()))
        last_title = m.group(2).strip()
        last_pos = m.start()
    sections.append((last_title, last_pos, len(text)))
    return sections

def _split_sentences(block: str) -> List[Sentence]:
    """
    Simple, fast sentence splitter. Not perfect, but robust enough for docs.
    Keeps code blocks intact (don’t split inside ```...```).
    """
    # Mask code blocks to prevent over-splitting
    masked = []
    idx = 0
    for m in _CODEBLOCK_RE.finditer(block):
        # split plain text before code
        plain = block[idx:m.start()]
        masked.extend(_SENTENCE_RE.split(plain))
        # keep the whole code block as a single “sentence”
        masked.append(block[m.start():m.end()])
        idx = m.end()
    # trailing text
    masked.extend(_SENTENCE_RE.split(block[idx:]))

    # Clean up empties
    return [s.strip() for s in masked if s and s.strip()]

def _estimate_tokens(s: str, token_counter: Optional[Callable[[str], int]] = None) -> int:
    """
    Estimate token count. If a tokenizer is provided (e.g., bge-m3),
    we use it; otherwise approximate via word count.
    """
    if token_counter:
        try:
            return int(token_counter(s))
        except Exception:
            pass
    # ~1 token per word is a coarse but safe upper bound for chunk sizing
    return max(1, len(s.split()))

def smart_chunks(
    text: str,
    *,
    max_tokens: int = 480,
    overlap_tokens: int = 40,
    token_counter: Optional[Callable[[str], int]] = None,
    respect_markdown: bool = True,
    section_prefix: bool = True,
) -> Iterable[str]:
    """
    Markdown-aware, sentence-aware, token-aware chunker.
    - Splits by Markdown sections (H1..H6), then by sentences.
    - Packs sentences greedily up to `max_tokens`.
    - Adds window overlap of ~`overlap_tokens` by sentence reuse.
    - Optionally prefixes chunks with the section title as context.

    Yields plain text chunks (strings).
    """
    if not text or not text.strip():
        return

    sections = _split_markdown_sections(text) if respect_markdown else [("Document", 0, len(text))]

    for title, s, e in sections:
        block = text[s:e].strip()
        if not block:
            continue
        sentences = _split_sentences(block)
        if not sentences:
            continue

        cur: List[str] = []
        cur_tok = 0

        i = 0
        while i < len(sentences):
            sent = sentences[i]
            st = _estimate_tokens(sent, token_counter)

            if cur and cur_tok + st > max_tokens:
                # emit current chunk
                chunk_body = " ".join(cur).strip()
                if section_prefix and title and title != "Document":
                    chunk = f"{title}\n\n{chunk_body}"
                else:
                    chunk = chunk_body
                if chunk:
                    yield chunk

                # overlap: reuse trailing sentences until ~overlap_tokens
                overlap_accum = 0
                cur = []
                cur_tok = 0
                j = i - 1
                while j >= 0 and overlap_accum < overlap_tokens:
                    prev = sentences[j]
                    pt = _estimate_tokens(prev, token_counter)
                    cur.insert(0, prev)          # prepend to new window
                    cur_tok += pt
                    overlap_accum += pt
                    j -= 1
                # do not advance i here; we’ll add current sentence next loop
            else:
                cur.append(sent)
                cur_tok += st
                i += 1

        # emit tail
        if cur:
            chunk_body = " ".join(cur).strip()
            if section_prefix and title and title != "Document":
                chunk = f"{title}\n\n{chunk_body}"
            else:
                chunk = chunk_body
            if chunk:
                yield chunk


def md_aware_chunks(text: str, **kwargs) -> Iterable[str]:
    """
    Alias for smart_chunks(text, respect_markdown=True).
    """
    kwargs.setdefault("respect_markdown", True)
    return smart_chunks(text, **kwargs)
