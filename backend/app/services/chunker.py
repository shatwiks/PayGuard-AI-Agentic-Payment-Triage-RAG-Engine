"""Text normalization and section-aware document chunker for PayGuard AI RAG."""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TextChunk(BaseModel):
    """Represents a normalized, section-aware document chunk."""
    chunk_index: int = Field(description="0-based sequence index within parent document")
    section_header: str = Field(description="Enclosing section title or header")
    content: str = Field(description="Normalized chunk text content")
    token_count: int = Field(description="Estimated token count")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk-level metadata")


class DocumentChunker:
    """Deterministic section-aware chunker for payment policy and troubleshooting guides."""

    # Heading patterns: markdown '# Header', '## Header', or structured 'Section X.X: Header', 'Rule 10.4 - Header'
    HEADER_REGEX = re.compile(
        r"^(?:#{1,6}\s+(.+)|((?:Section|Rule|Article)\s+[0-9A-Za-z_.-]+(?::|\s+-)[^\n]{0,120}))$",
        re.MULTILINE,
    )

    def __init__(
        self,
        target_chunk_size: int = 600,
        chunk_overlap: int = 80,
        min_chunk_size: int = 80,
    ):
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def normalize_text(self, text: str) -> str:
        """Normalizes text while preserving casing, technical codes, and paragraph semantics."""
        if not text:
            return ""
        # 1. Standardize line endings
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        # 2. Strip trailing whitespace on each line
        lines = [line.rstrip() for line in normalized.split("\n")]
        # 3. Collapse multiple blank lines (> 2) into 2
        collapsed: List[str] = []
        blank_count = 0
        for line in lines:
            if not line.strip():
                blank_count += 1
                if blank_count <= 2:
                    collapsed.append("")
            else:
                blank_count = 0
                collapsed.append(line)
        return "\n".join(collapsed).strip()

    def estimate_tokens(self, text: str) -> int:
        """Estimates token count using standard ~4 chars/token heuristic or word boundary."""
        if not text:
            return 0
        words = len(text.split())
        chars = len(text)
        return max(words, chars // 4)

    def split_document(
        self,
        text: str,
        document_title: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> List[TextChunk]:
        """Splits normalized text into section-aware chunks with provenance tracking."""
        normalized = self.normalize_text(text)
        if not normalized:
            return []

        # Find all section headers and their start positions
        sections: List[Dict[str, Any]] = []
        matches = list(self.HEADER_REGEX.finditer(normalized))

        if not matches:
            # No explicit markdown/section headers: treat entire document as one or more paragraphs
            default_header = document_title or "General"
            sections.append({
                "header": default_header,
                "body": normalized,
            })
        else:
            # Handle text before the first header (preamble)
            first_match = matches[0]
            if first_match.start() > 0:
                preamble = normalized[:first_match.start()].strip()
                if preamble:
                    sections.append({
                        "header": f"{document_title} - Overview" if document_title else "Overview",
                        "body": preamble,
                    })

            for idx, match in enumerate(matches):
                raw_header = match.group(1) or match.group(2)
                header = raw_header.strip().lstrip("#").strip() if raw_header else "Section"
                start_body = match.end()
                end_body = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized)
                body = normalized[start_body:end_body].strip()
                if body:
                    sections.append({
                        "header": header,
                        "body": body,
                    })

        # Process each section into chunks based on target_chunk_size
        chunks: List[TextChunk] = []
        chunk_index = 0

        for sec in sections:
            header = sec["header"]
            body = sec["body"]

            # If section body fits comfortably in target size, keep it whole
            if len(body) <= self.target_chunk_size + self.chunk_overlap:
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_index,
                        section_header=header,
                        content=body,
                        token_count=self.estimate_tokens(body),
                        metadata={
                            "document_title": document_title,
                            "source_id": source_id,
                            "split_type": "whole_section",
                        },
                    )
                )
                chunk_index += 1
            else:
                # Sub-split larger section by paragraphs
                paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
                current_buffer = ""

                for p in paragraphs:
                    if not current_buffer:
                        current_buffer = p
                    elif len(current_buffer) + len(p) + 2 <= self.target_chunk_size:
                        current_buffer += "\n\n" + p
                    else:
                        # Flush current buffer
                        chunks.append(
                            TextChunk(
                                chunk_index=chunk_index,
                                section_header=header,
                                content=current_buffer,
                                token_count=self.estimate_tokens(current_buffer),
                                metadata={
                                    "document_title": document_title,
                                    "source_id": source_id,
                                    "split_type": "paragraph_split",
                                },
                            )
                        )
                        chunk_index += 1
                        # Maintain overlap from tail of buffer if configured
                        if self.chunk_overlap > 0 and len(current_buffer) > self.chunk_overlap:
                            overlap_text = current_buffer[-self.chunk_overlap:]
                            # Trim to last space to avoid cutting words
                            space_idx = overlap_text.find(" ")
                            if space_idx != -1:
                                overlap_text = overlap_text[space_idx + 1:]
                            current_buffer = overlap_text + "\n\n" + p
                        else:
                            current_buffer = p

                if current_buffer.strip():
                    chunks.append(
                        TextChunk(
                            chunk_index=chunk_index,
                            section_header=header,
                            content=current_buffer.strip(),
                            token_count=self.estimate_tokens(current_buffer.strip()),
                            metadata={
                                "document_title": document_title,
                                "source_id": source_id,
                                "split_type": "paragraph_tail",
                            },
                        )
                    )
                    chunk_index += 1

        return chunks
