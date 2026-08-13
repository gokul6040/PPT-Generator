"""Split long text into slide-sized chunks without summarizing."""
import re

from src.config import BODY_GAP_CHAR_COST


def _block_count(text: str) -> int:
    return len([line for line in text.split("\n") if line.strip()])


def _effective_len(text: str, gap_chars: int = BODY_GAP_CHAR_COST) -> int:
    """Text length + virtual cost of inter-block spacing rendered in the PPT."""
    blocks = _block_count(text)
    return len(text) + max(0, blocks - 1) * gap_chars


def _join_paragraphs(current: str, para: str) -> str:
    """Join blocks — single-line rows use one newline (no blank spacer line)."""
    if not current:
        return para
    if "\n" not in current and "\n" not in para:
        return current + "\n" + para
    return current + "\n\n" + para


def split_text_for_slides(text: str, max_chars: int = 1400) -> list[str]:
    """
    Split text into chunks that fit within max_chars.
    Splits at paragraph boundaries first, then sentence boundaries,
    then word boundaries. Preserves original order and wording.
    """
    text = text.strip()
    if not text:
        return []

    if _effective_len(text) <= max_chars:
        return [text]

    # Try paragraph splits
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if len(paragraphs) == 1:
        # Single block — fall through to sentence splitting
        paragraphs = [p.strip() for p in re.split(r"\n", text) if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(para) > max_chars:
            # Paragraph itself is too long — split by sentences
            sentences = _split_sentences(para)
            for sent in sentences:
                if len(sent) > max_chars:
                    # Sentence too long — split by words
                    word_chunks = _split_by_words(sent, max_chars)
                    for wc in word_chunks:
                        if current and len(current) + 1 + len(wc) > max_chars:
                            chunks.append(current.strip())
                            current = wc
                        else:
                            current = (current + "\n" + wc).strip() if current else wc
                else:
                    candidate = _join_paragraphs(current, sent) if current else sent
                    if _effective_len(candidate) > max_chars:
                        chunks.append(current.strip())
                        current = sent
                    else:
                        current = candidate
        else:
            candidate = _join_paragraphs(current, para) if current else para
            if _effective_len(candidate) > max_chars:
                chunks.append(current.strip())
                current = para
            else:
                current = candidate

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _split_sentences(text: str) -> list[str]:
    # Split on . ! ? followed by whitespace or end
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _split_by_words(text: str, max_chars: int) -> list[str]:
    words = text.split()
    chunks = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > max_chars:
            if current:
                chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
