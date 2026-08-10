"""Knowledge-base loading and chunking for Agent 3."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_HEADING = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


@dataclass
class KnowledgeChunk:
    """One retrievable passage."""

    doc_id: str
    title: str
    source: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """Pull simple ``key: value`` YAML frontmatter off the top of a document."""
    match = _FRONTMATTER.match(raw)
    if not match:
        return {}, raw
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("\"'")
    return meta, raw[match.end() :]


def chunk_markdown(
    raw: str, *, source: str, max_chars: int = 900, overlap_sentences: int = 1
) -> list[KnowledgeChunk]:
    """Split a markdown document on headings, then pack sections into chunks.

    Heading-aware splitting keeps each chunk about one topic ("banks never ask
    for your OTP"), which matters more for retrieval quality than uniform
    chunk size.
    """
    meta, body = _parse_frontmatter(raw)
    doc_title = meta.get("title") or Path(source).stem.replace("-", " ").title()
    category = meta.get("category", "general")
    authority = meta.get("authority", "internal")

    sections: list[tuple[str, str]] = []
    matches = list(_HEADING.finditer(body))
    if not matches:
        sections.append((doc_title, body.strip()))
    else:
        if matches[0].start() > 0:
            preamble = body[: matches[0].start()].strip()
            if preamble:
                sections.append((doc_title, preamble))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
            heading = match.group(2).strip()
            content = body[match.end() : end].strip()
            if content:
                sections.append((heading, content))

    chunks: list[KnowledgeChunk] = []
    for heading, content in sections:
        for part in _pack(content, max_chars=max_chars, overlap_sentences=overlap_sentences):
            digest = hashlib.sha1(f"{source}:{heading}:{part[:80]}".encode()).hexdigest()[:16]
            chunks.append(
                KnowledgeChunk(
                    doc_id=digest,
                    title=f"{doc_title} — {heading}" if heading != doc_title else doc_title,
                    source=source,
                    content=part,
                    metadata={
                        "category": category,
                        "authority": authority,
                        "heading": heading,
                        "document": doc_title,
                    },
                )
            )
    return chunks


def _pack(text: str, *, max_chars: int, overlap_sentences: int) -> list[str]:
    """Greedily pack sentences into ``max_chars`` windows with a small overlap."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n(?=[-*]\s)", text) if s.strip()]
    if not sentences:
        return []

    packed: list[str] = []
    current: list[str] = []
    length = 0
    for sentence in sentences:
        if current and length + len(sentence) > max_chars:
            packed.append(" ".join(current))
            current = current[-overlap_sentences:] if overlap_sentences else []
            length = sum(len(item) for item in current)
        current.append(sentence)
        length += len(sentence)
    if current:
        packed.append(" ".join(current))
    return packed


def load_knowledge_base(directory: Path) -> list[KnowledgeChunk]:
    """Load and chunk every markdown file under ``directory``."""
    if not directory.exists():
        logger.warning("knowledge_base_missing", path=str(directory))
        return []

    chunks: list[KnowledgeChunk] = []
    for path in sorted(directory.rglob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("knowledge_doc_unreadable", path=str(path), error=str(exc))
            continue
        chunks.extend(chunk_markdown(raw, source=path.name))

    logger.info(
        "knowledge_base_loaded", documents=len(list(directory.rglob("*.md"))), chunks=len(chunks)
    )
    return chunks
