"""Hierarchical document chunker with table preservation and metadata extraction for PayGuard AI RAG."""

from datetime import datetime
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.app.core.config import settings


class TextChunk(BaseModel):
    """Represents a normalized, section-aware document chunk."""
    chunk_index: int = Field(description="0-based sequence index within document")
    section_header: str = Field(description="Enclosing section title or header")
    content: str = Field(description="Normalized chunk text content")
    token_count: int = Field(description="Estimated token count")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk-level metadata")
    chunk_type: str = Field(default="standalone", description="Chunk hierarchy type: parent, child, or standalone")
    parent_index: Optional[int] = Field(default=None, description="Index of parent chunk if this is a child chunk")
    section_title: Optional[str] = Field(default=None, description="Clean section title")
    content_hash: Optional[str] = Field(default=None, description="SHA-256 hash of chunk content")


class HierarchicalChunkResult(BaseModel):
    """Container for parent chunks, child chunks, and combined chunk collection."""
    parents: List[TextChunk] = Field(default_factory=list, description="Coarse parent chunks for surrounding context")
    children: List[TextChunk] = Field(default_factory=list, description="Focused child chunks for semantic/lexical retrieval")
    all_chunks: List[TextChunk] = Field(default_factory=list, description="Combined ordered list of all chunks")


class DocumentChunker:
    """Production-grade hierarchical section and table-aware document chunker."""

    # Heading patterns: markdown '# Header', '## Header', or structured 'Section X.X: Header', 'Rule 10.4 - Header'
    HEADER_REGEX = re.compile(
        r"^(?:#{1,6}\s+(.+)|((?:Section|Rule|Article)\s+[0-9A-Za-z_.-]+(?::|\s+-)[^\n]{0,120}))$",
        re.MULTILINE,
    )

    # Markdown table patterns
    TABLE_ROW_REGEX = re.compile(r"^\s*\|.*\|\s*$")
    TABLE_DELIMITER_REGEX = re.compile(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$")

    # Payment scheme patterns
    SCHEME_REGEX = re.compile(
        r"\b(Visa|Mastercard|NACHA|Amex|American Express|Discover|UPI|FedNow|ACH)\b",
        re.IGNORECASE,
    )

    # Condition & return code patterns
    CONDITION_CODE_REGEX = re.compile(
        r"\b(?:(?:Condition|Reason Code|Reason code|Dispute Code|Rule|Error Code|Code)\s+([0-9]{1,4}(?:\.[0-9]{1,2})?)|(R[0-9]{2}))\b",
        re.IGNORECASE,
    )

    # Date pattern (YYYY-MM-DD or YYYY.MM.DD)
    DATE_REGEX = re.compile(
        r"\b(20[2-9][0-9][-/.][0-1][0-9][-/.][0-3][0-9])\b"
    )

    def __init__(
        self,
        target_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        min_chunk_size: int = 80,
        target_parent_chunk_size: Optional[int] = None,
        parent_chunk_overlap: Optional[int] = None,
        target_child_chunk_size: Optional[int] = None,
        child_chunk_overlap: Optional[int] = None,
        table_aware_enabled: Optional[bool] = None,
    ):
        # Configure parent & child target sizes
        self.target_parent_chunk_size = (
            target_parent_chunk_size
            if target_parent_chunk_size is not None
            else getattr(settings, "CHUNK_PARENT_SIZE", 1000)
        )
        self.parent_chunk_overlap = (
            parent_chunk_overlap
            if parent_chunk_overlap is not None
            else getattr(settings, "CHUNK_PARENT_OVERLAP", 100)
        )
        self.target_child_chunk_size = (
            target_child_chunk_size
            if target_child_chunk_size is not None
            else getattr(settings, "CHUNK_CHILD_SIZE", 200)
        )
        self.child_chunk_overlap = (
            child_chunk_overlap
            if child_chunk_overlap is not None
            else getattr(settings, "CHUNK_CHILD_OVERLAP", 30)
        )
        self.table_aware_enabled = (
            table_aware_enabled
            if table_aware_enabled is not None
            else getattr(settings, "CHUNK_TABLE_AWARE_ENABLED", True)
        )

        # Legacy compatibility settings
        self.target_chunk_size = target_chunk_size or 600
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else 80
        self.min_chunk_size = min_chunk_size

    def normalize_text(self, text: str) -> str:
        """Normalizes text while preserving casing, technical codes, tables, and paragraph semantics."""
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
        """Estimates token count using consistent word/symbol boundaries with character fallback (~4 chars/token)."""
        if not text:
            return 0
        # Split on whitespace and technical punctuation tokens
        tokens = re.findall(r"\w+|[^\w\s]", text)
        chars = len(text)
        return max(len(tokens), chars // 4, 1)

    def compute_content_hash(self, content: str) -> str:
        """Generates deterministic SHA-256 hash for chunk deduplication and integrity."""
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    def extract_metadata(
        self,
        text: str,
        document_title: Optional[str] = None,
        source_id: Optional[str] = None,
        base_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extracts structured payment domain metadata from text and trusted headers."""
        meta: Dict[str, Any] = dict(base_metadata or {})
        combined_text = f"{document_title or ''} {text}"

        # 1. Payment Scheme
        if "scheme" not in meta:
            scheme_match = self.SCHEME_REGEX.search(combined_text)
            if scheme_match:
                raw_scheme = scheme_match.group(1)
                upper_scheme = raw_scheme.upper()
                if upper_scheme in ("ACH", "UPI", "NACHA"):
                    meta["scheme"] = upper_scheme
                elif upper_scheme in ("AMEX", "AMERICAN EXPRESS"):
                    meta["scheme"] = "Amex"
                else:
                    meta["scheme"] = raw_scheme.capitalize()

        # 2. Condition or Return Code
        if "condition_code" not in meta:
            code_match = self.CONDITION_CODE_REGEX.search(combined_text)
            if code_match:
                meta["condition_code"] = (code_match.group(1) or code_match.group(2)).upper()

        # 3. Effective Date (strictly validated against Gregorian calendar)
        if "effective_date" not in meta:
            date_match = self.DATE_REGEX.search(combined_text)
            if date_match:
                raw_date = date_match.group(1).replace(".", "-").replace("/", "-")
                try:
                    parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                    meta["effective_date"] = parsed_date.isoformat()
                except ValueError:
                    # Ignore invalid calendar dates (e.g., 2026-02-31)
                    pass

        # 4. Source Document
        if "source_document" not in meta and document_title:
            meta["source_document"] = document_title

        # 5. Source ID
        if "source_id" not in meta and source_id:
            meta["source_id"] = source_id

        return meta

    def _split_into_sections(self, normalized_text: str, document_title: Optional[str] = None) -> List[Dict[str, str]]:
        """Parses document into meaningful sections based on markdown and structured headings."""
        sections: List[Dict[str, str]] = []
        matches = list(self.HEADER_REGEX.finditer(normalized_text))

        if not matches:
            default_header = document_title or "General Policy"
            sections.append({
                "header": default_header,
                "body": normalized_text,
            })
            return sections

        # Handle text preceding first header
        first_match = matches[0]
        if first_match.start() > 0:
            preamble = normalized_text[:first_match.start()].strip()
            if preamble:
                sections.append({
                    "header": f"{document_title} - Overview" if document_title else "Overview",
                    "body": preamble,
                })

        for idx, match in enumerate(matches):
            raw_header = match.group(1) or match.group(2)
            header = raw_header.strip().lstrip("#").strip() if raw_header else "Section"
            start_body = match.end()
            end_body = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized_text)
            body = normalized_text[start_body:end_body].strip()
            if body:
                sections.append({
                    "header": header,
                    "body": body,
                })

        return sections

    def _split_table_into_chunks(self, table_lines: List[str], target_tokens: int) -> List[str]:
        """Splits an oversized Markdown table across rows while repeating header and delimiter lines."""
        if len(table_lines) <= 2:
            return ["\n".join(table_lines)]

        header_line = table_lines[0]
        delimiter_line = table_lines[1]
        header_block = f"{header_line}\n{delimiter_line}"
        header_tokens = self.estimate_tokens(header_block)

        data_rows = table_lines[2:]
        chunks: List[str] = []
        current_rows: List[str] = []
        current_tokens = header_tokens

        for row in data_rows:
            row_tokens = self.estimate_tokens(row)
            if current_rows and (current_tokens + row_tokens > target_tokens):
                chunk_table = f"{header_block}\n" + "\n".join(current_rows)
                chunks.append(chunk_table)
                current_rows = [row]
                current_tokens = header_tokens + row_tokens
            else:
                current_rows.append(row)
                current_tokens += row_tokens

        if current_rows:
            chunk_table = f"{header_block}\n" + "\n".join(current_rows)
            chunks.append(chunk_table)

        return chunks

    def _extract_paragraphs_and_tables(self, body_text: str) -> List[Tuple[str, str]]:
        """Parses a section body into blocks of plain paragraphs and structured Markdown tables."""
        lines = body_text.split("\n")
        blocks: List[Tuple[str, str]] = []
        current_text_lines: List[str] = []
        current_table_lines: List[str] = []
        in_table = False

        for line in lines:
            is_table_row = bool(self.TABLE_ROW_REGEX.match(line))
            if is_table_row and self.table_aware_enabled:
                if not in_table:
                    # Flush accumulated text lines
                    if current_text_lines:
                        text_content = "\n".join(current_text_lines).strip()
                        if text_content:
                            blocks.append(("text", text_content))
                        current_text_lines = []
                    in_table = True
                current_table_lines.append(line)
            else:
                if in_table:
                    # Flush table
                    if len(current_table_lines) >= 2 and self.TABLE_DELIMITER_REGEX.match(current_table_lines[1]):
                        blocks.append(("table", "\n".join(current_table_lines)))
                    else:
                        # Not a valid table; treat as regular text
                        current_text_lines.extend(current_table_lines)
                    current_table_lines = []
                    in_table = False
                current_text_lines.append(line)

        # Flush final blocks
        if in_table and current_table_lines:
            if len(current_table_lines) >= 2 and self.TABLE_DELIMITER_REGEX.match(current_table_lines[1]):
                blocks.append(("table", "\n".join(current_table_lines)))
            else:
                current_text_lines.extend(current_table_lines)

        if current_text_lines:
            text_content = "\n".join(current_text_lines).strip()
            if text_content:
                blocks.append(("text", text_content))

        return blocks

    def split_hierarchical(
        self,
        text: str,
        document_title: Optional[str] = None,
        source_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HierarchicalChunkResult:
        """Performs production parent-child hierarchical chunking with table preservation and metadata extraction."""
        normalized = self.normalize_text(text)
        if not normalized:
            return HierarchicalChunkResult()

        sections = self._split_into_sections(normalized, document_title=document_title)
        parent_chunks: List[TextChunk] = []
        child_chunks: List[TextChunk] = []
        global_chunk_index = 0

        for sec in sections:
            header = sec["header"]
            body = sec["body"]
            sec_tokens = self.estimate_tokens(body)

            # Step 1: Create Parent Chunks (~1000 tokens)
            section_parents: List[str] = []
            if sec_tokens <= self.target_parent_chunk_size + self.parent_chunk_overlap:
                section_parents.append(body)
            else:
                # Split large section into overlapping parent segments along paragraphs
                paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
                curr_parent = ""
                curr_parent_tokens = 0

                for p in paragraphs:
                    p_tokens = self.estimate_tokens(p)
                    if not curr_parent:
                        curr_parent = p
                        curr_parent_tokens = p_tokens
                    elif curr_parent_tokens + p_tokens <= self.target_parent_chunk_size:
                        curr_parent += "\n\n" + p
                        curr_parent_tokens += p_tokens
                    else:
                        section_parents.append(curr_parent)
                        # Overlap from tail of previous buffer
                        if self.parent_chunk_overlap > 0:
                            tail_words = curr_parent.split()[-self.parent_chunk_overlap:]
                            curr_parent = " ".join(tail_words) + "\n\n" + p
                            curr_parent_tokens = self.estimate_tokens(curr_parent)
                        else:
                            curr_parent = p
                            curr_parent_tokens = p_tokens

                if curr_parent.strip():
                    section_parents.append(curr_parent.strip())

            # Step 2: For each Parent Chunk, generate Child Chunks (~200 tokens)
            for p_text in section_parents:
                parent_idx = global_chunk_index
                global_chunk_index += 1

                p_tokens = self.estimate_tokens(p_text)
                parent_meta = self.extract_metadata(
                    text=p_text,
                    document_title=document_title,
                    source_id=source_id,
                    base_metadata=metadata,
                )
                parent_meta.update({
                    "document_title": document_title,
                    "source_id": source_id,
                    "section_title": header,
                    "chunk_type": "parent",
                })

                parent_content = (
                    f"## {header}\n\n{p_text}"
                    if not p_text.startswith(f"## {header}") and not p_text.startswith(f"# {header}")
                    else p_text
                )
                parent_chunk = TextChunk(
                    chunk_index=parent_idx,
                    section_header=header,
                    section_title=header,
                    content=parent_content,
                    token_count=self.estimate_tokens(parent_content),
                    chunk_type="parent",
                    parent_index=None,
                    content_hash=self.compute_content_hash(parent_content),
                    metadata=parent_meta,
                )
                parent_chunks.append(parent_chunk)

                # Generate child chunks from parent text
                blocks = self._extract_paragraphs_and_tables(p_text)
                child_contents: List[str] = []

                for block_type, block_content in blocks:
                    if block_type == "table":
                        table_lines = [line for line in block_content.split("\n") if line.strip()]
                        table_tokens = self.estimate_tokens(block_content)
                        if table_tokens <= self.target_child_chunk_size:
                            child_contents.append(block_content)
                        else:
                            split_tables = self._split_table_into_chunks(table_lines, self.target_child_chunk_size)
                            child_contents.extend(split_tables)
                    else:
                        # Plain text paragraphs
                        paras = [p.strip() for p in block_content.split("\n\n") if p.strip()]
                        curr_child = ""
                        curr_child_tokens = 0

                        for p in paras:
                            p_tok = self.estimate_tokens(p)
                            if not curr_child:
                                curr_child = p
                                curr_child_tokens = p_tok
                            elif curr_child_tokens + p_tok <= self.target_child_chunk_size:
                                curr_child += "\n\n" + p
                                curr_child_tokens += p_tok
                            else:
                                child_contents.append(curr_child)
                                # Overlap from tail of buffer (bounded so it never exceeds one-third of the target)
                                max_allowed_overlap = max(1, self.target_child_chunk_size // 3)
                                eff_overlap = min(self.child_chunk_overlap, max_allowed_overlap)
                                words = curr_child.split()
                                if eff_overlap > 0 and len(words) > eff_overlap:
                                    tail_words = words[-eff_overlap:]
                                    curr_child = " ".join(tail_words) + "\n\n" + p
                                    curr_child_tokens = self.estimate_tokens(curr_child)
                                else:
                                    curr_child = p
                                    curr_child_tokens = p_tok

                        if curr_child.strip():
                            child_contents.append(curr_child.strip())

                # If no child chunks generated (e.g. empty or single block), use parent text directly
                if not child_contents:
                    child_contents = [p_text]

                for c_text in child_contents:
                    child_idx = global_chunk_index
                    global_chunk_index += 1

                    c_tokens = self.estimate_tokens(c_text)
                    child_meta = self.extract_metadata(
                        text=c_text,
                        document_title=document_title,
                        source_id=source_id,
                        base_metadata=parent_meta,
                    )
                    child_meta.update({
                        "document_title": document_title,
                        "source_id": source_id,
                        "section_title": header,
                        "parent_chunk_index": parent_idx,
                        "chunk_type": "child",
                    })

                    child_chunk = TextChunk(
                        chunk_index=child_idx,
                        section_header=header,
                        section_title=header,
                        content=c_text,
                        token_count=c_tokens,
                        chunk_type="child",
                        parent_index=parent_idx,
                        content_hash=self.compute_content_hash(c_text),
                        metadata=child_meta,
                    )
                    child_chunks.append(child_chunk)

        all_chunks = parent_chunks + child_chunks
        return HierarchicalChunkResult(
            parents=parent_chunks,
            children=child_chunks,
            all_chunks=all_chunks,
        )

    def split_document(
        self,
        text: str,
        document_title: Optional[str] = None,
        source_id: Optional[str] = None,
        hierarchical: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[TextChunk]:
        """Splits normalized text into section-aware chunks with backward compatibility."""
        if hierarchical:
            res = self.split_hierarchical(
                text=text,
                document_title=document_title,
                source_id=source_id,
                metadata=metadata,
            )
            return res.all_chunks

        normalized = self.normalize_text(text)
        if not normalized:
            return []

        # Find all section headers and their start positions
        sections: List[Dict[str, Any]] = []
        matches = list(self.HEADER_REGEX.finditer(normalized))

        if not matches:
            default_header = document_title or "General"
            sections.append({
                "header": default_header,
                "body": normalized,
            })
        else:
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

        chunks: List[TextChunk] = []
        chunk_index = 0

        for sec in sections:
            header = sec["header"]
            body = sec["body"]

            if len(body) <= self.target_chunk_size + self.chunk_overlap:
                meta = self.extract_metadata(body, document_title, source_id, metadata)
                meta.update({
                    "document_title": document_title,
                    "source_id": source_id,
                    "split_type": "whole_section",
                })
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_index,
                        section_header=header,
                        section_title=header,
                        content=body,
                        token_count=self.estimate_tokens(body),
                        content_hash=self.compute_content_hash(body),
                        chunk_type="standalone",
                        metadata=meta,
                    )
                )
                chunk_index += 1
            else:
                paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
                current_buffer = ""

                for p in paragraphs:
                    if not current_buffer:
                        current_buffer = p
                    elif len(current_buffer) + len(p) + 2 <= self.target_chunk_size:
                        current_buffer += "\n\n" + p
                    else:
                        meta = self.extract_metadata(current_buffer, document_title, source_id, metadata)
                        meta.update({
                            "document_title": document_title,
                            "source_id": source_id,
                            "split_type": "paragraph_split",
                        })
                        chunks.append(
                            TextChunk(
                                chunk_index=chunk_index,
                                section_header=header,
                                section_title=header,
                                content=current_buffer,
                                token_count=self.estimate_tokens(current_buffer),
                                content_hash=self.compute_content_hash(current_buffer),
                                chunk_type="standalone",
                                metadata=meta,
                            )
                        )
                        chunk_index += 1
                        if self.chunk_overlap > 0 and len(current_buffer) > self.chunk_overlap:
                            overlap_text = current_buffer[-self.chunk_overlap:]
                            space_idx = overlap_text.find(" ")
                            if space_idx != -1:
                                overlap_text = overlap_text[space_idx + 1:]
                            current_buffer = overlap_text + "\n\n" + p
                        else:
                            current_buffer = p

                if current_buffer.strip():
                    meta = self.extract_metadata(current_buffer.strip(), document_title, source_id, metadata)
                    meta.update({
                        "document_title": document_title,
                        "source_id": source_id,
                        "split_type": "paragraph_tail",
                    })
                    chunks.append(
                        TextChunk(
                            chunk_index=chunk_index,
                            section_header=header,
                            section_title=header,
                            content=current_buffer.strip(),
                            token_count=self.estimate_tokens(current_buffer.strip()),
                            content_hash=self.compute_content_hash(current_buffer.strip()),
                            chunk_type="standalone",
                            metadata=meta,
                        )
                    )
                    chunk_index += 1

        return chunks
