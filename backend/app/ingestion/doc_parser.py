import io
import csv
import json
import logging
import re
from typing import List, Dict, Any, Optional

import pypdf
import docx

from backend.app.retrieval.chunker import Chunk

logger = logging.getLogger("yt_agent.doc_parser")


class DocumentCommentsParser:
    """
    Parses user comments from structured/tabular documents (PDF, DOCX, CSV, JSON).
    Extracts author and comment text with automatic column detection.
    """

    @staticmethod
    def parse(file_bytes: bytes, filename: str) -> List[Dict[str, str]]:
        fn_lower = filename.lower()
        if fn_lower.endswith(".csv"):
            return DocumentCommentsParser._parse_csv(file_bytes, filename)
        elif fn_lower.endswith(".json"):
            return DocumentCommentsParser._parse_json(file_bytes, filename)
        elif fn_lower.endswith(".docx"):
            return DocumentCommentsParser._parse_docx(file_bytes, filename)
        elif fn_lower.endswith(".pdf"):
            return DocumentCommentsParser._parse_pdf(file_bytes, filename)
        elif fn_lower.endswith(".txt"):
            return DocumentCommentsParser._parse_txt(file_bytes, filename)
        else:
            raise ValueError(f"Unsupported file format '{filename}'. Supported: .pdf, .docx, .csv, .json, .txt")

    @staticmethod
    def _parse_csv(file_bytes: bytes, filename: str) -> List[Dict[str, str]]:
        content = file_bytes.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(content))
        results = []

        # Find author and text column names
        fieldnames = reader.fieldnames or []
        text_col = next((f for f in fieldnames if f.lower() in ("text", "comment", "comment_text", "feedback", "body", "content", "message")), None)
        author_col = next((f for f in fieldnames if f.lower() in ("author", "user", "username", "sender", "name")), None)

        if not text_col:
            # Fall back to first non-author column or column 1
            text_col = fieldnames[1] if len(fieldnames) > 1 else fieldnames[0]

        for idx, row in enumerate(reader, 1):
            text_val = (row.get(text_col) or "").strip()
            if not text_val:
                continue
            author_val = (row.get(author_col) or f"User_{idx}").strip() if author_col else f"User_{idx}"
            results.append({
                "author": author_val,
                "text": text_val,
                "source": filename,
            })
        return results

    @staticmethod
    def _parse_json(file_bytes: bytes, filename: str) -> List[Dict[str, str]]:
        content = file_bytes.decode("utf-8", errors="replace")
        data = json.loads(content)
        if isinstance(data, dict):
            # If wrapped in a top-level key like {"comments": [...]}
            for k in ("comments", "items", "data", "feedback", "reviews"):
                if k in data and isinstance(data[k], list):
                    data = data[k]
                    break
            else:
                data = [data]

        results = []
        for idx, item in enumerate(data, 1):
            if not isinstance(item, dict):
                continue
            text_val = item.get("text") or item.get("comment") or item.get("content") or item.get("feedback") or ""
            text_val = str(text_val).strip()
            if not text_val:
                continue
            author_val = item.get("author") or item.get("user") or item.get("name") or f"User_{idx}"
            results.append({
                "author": str(author_val).strip(),
                "text": text_val,
                "source": filename,
            })
        return results

    @staticmethod
    def _parse_docx(file_bytes: bytes, filename: str) -> List[Dict[str, str]]:
        doc = docx.Document(io.BytesIO(file_bytes))
        results = []

        # 1. First inspect Word tables (Tabular Option B)
        if doc.tables:
            for table in doc.tables:
                rows = list(table.rows)
                if not rows:
                    continue
                header_cells = [cell.text.strip().lower() for cell in rows[0].cells]
                
                # Check for header names
                text_idx = -1
                author_idx = -1
                for i, h in enumerate(header_cells):
                    if h in ("text", "comment", "comment text", "feedback", "content", "review"):
                        text_idx = i
                    elif h in ("author", "user", "name", "commenter", "username"):
                        author_idx = i

                start_row = 1 if (text_idx != -1 or author_idx != -1) else 0
                if text_idx == -1:
                    text_idx = 1 if len(rows[0].cells) > 1 else 0
                if author_idx == -1 and len(rows[0].cells) > 1:
                    author_idx = 0

                for r_idx, row in enumerate(rows[start_row:], start_row + 1):
                    cells = row.cells
                    if not cells or len(cells) <= text_idx:
                        continue
                    text_val = cells[text_idx].text.strip()
                    if not text_val:
                        continue
                    author_val = cells[author_idx].text.strip() if (author_idx != -1 and len(cells) > author_idx) else f"User_{r_idx}"
                    results.append({
                        "author": author_val or f"User_{r_idx}",
                        "text": text_val,
                        "source": filename,
                    })

        # 2. If no tables found, extract paragraph lines
        if not results:
            for p_idx, p in enumerate(doc.paragraphs, 1):
                raw = p.text.strip()
                if not raw or len(raw) < 5:
                    continue
                # Check for "Author: Text" pattern
                if ":" in raw and len(raw.split(":", 1)[0]) < 30:
                    parts = raw.split(":", 1)
                    results.append({
                        "author": parts[0].strip(),
                        "text": parts[1].strip(),
                        "source": filename,
                    })
                else:
                    results.append({
                        "author": f"User_{p_idx}",
                        "text": raw,
                        "source": filename,
                    })

        return results

    @staticmethod
    def _parse_pdf(file_bytes: bytes, filename: str) -> List[Dict[str, str]]:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        results = []
        full_lines = []

        for page in reader.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                l = line.strip()
                if l:
                    full_lines.append(l)

        # Look for tabular patterns (e.g., delimited by | or tabs or Author: Comment)
        for idx, line in enumerate(full_lines, 1):
            if "|" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2:
                    results.append({
                        "author": parts[0],
                        "text": " ".join(parts[1:]),
                        "source": filename,
                    })
                    continue
            if "\t" in line:
                parts = [p.strip() for p in line.split("\t") if p.strip()]
                if len(parts) >= 2:
                    results.append({
                        "author": parts[0],
                        "text": " ".join(parts[1:]),
                        "source": filename,
                    })
                    continue
            if ":" in line and len(line.split(":", 1)[0]) < 25:
                parts = line.split(":", 1)
                results.append({
                    "author": parts[0].strip(),
                    "text": parts[1].strip(),
                    "source": filename,
                })
                continue

            # General line if not matched
            if len(line) > 10:
                results.append({
                    "author": f"User_{idx}",
                    "text": line,
                    "source": filename,
                })

        return results

    @staticmethod
    def _parse_txt(file_bytes: bytes, filename: str) -> List[Dict[str, str]]:
        content = file_bytes.decode("utf-8", errors="replace")
        results = []
        for idx, line in enumerate(content.splitlines(), 1):
            line = line.strip()
            if not line or len(line) < 5:
                continue
            if ":" in line and len(line.split(":", 1)[0]) < 30:
                parts = line.split(":", 1)
                results.append({
                    "author": parts[0].strip(),
                    "text": parts[1].strip(),
                    "source": filename,
                })
            else:
                results.append({
                    "author": f"User_{idx}",
                    "text": line,
                    "source": filename,
                })
        return results


class ReferenceDocumentParser:
    """
    Parses knowledge/reference documents (PDF, DOCX, TXT, SRT)
    into semantic chunks ready for vector and BM25 hybrid indexing.
    """

    @staticmethod
    def parse_to_chunks(file_bytes: bytes, filename: str, chunk_size: int = 350) -> List[Chunk]:
        fn_lower = filename.lower()
        if fn_lower.endswith(".pdf"):
            return ReferenceDocumentParser._parse_pdf(file_bytes, chunk_size)
        elif fn_lower.endswith(".docx"):
            return ReferenceDocumentParser._parse_docx(file_bytes, chunk_size)
        elif fn_lower.endswith(".srt"):
            return ReferenceDocumentParser._parse_srt(file_bytes)
        else:
            return ReferenceDocumentParser._parse_txt(file_bytes, chunk_size)

    @staticmethod
    def _parse_pdf(file_bytes: bytes, chunk_size: int) -> List[Chunk]:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        chunks = []
        for p_idx, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            words = text.split()
            # Split words into chunk_size pieces per page
            for i in range(0, len(words), chunk_size):
                piece = " ".join(words[i:i + chunk_size])
                # start_time represents page index in seconds for consistency
                chunks.append(Chunk(
                    text=f"[Page {p_idx}] {piece}",
                    start_time=float(p_idx),
                    end_time=float(p_idx),
                    token_count=len(words[i:i + chunk_size]),
                ))
        return chunks

    @staticmethod
    def _parse_docx(file_bytes: bytes, chunk_size: int) -> List[Chunk]:
        doc = docx.Document(io.BytesIO(file_bytes))
        chunks = []
        current_section = "General"
        accumulated_words = []
        section_idx = 1

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            if p.style.name.startswith("Heading"):
                current_section = text
                section_idx += 1

            words = text.split()
            accumulated_words.extend(words)

            if len(accumulated_words) >= chunk_size:
                piece = " ".join(accumulated_words)
                chunks.append(Chunk(
                    text=f"[{current_section}] {piece}",
                    start_time=float(section_idx),
                    end_time=float(section_idx),
                    token_count=len(accumulated_words),
                ))
                accumulated_words = []

        if accumulated_words:
            chunks.append(Chunk(
                text=f"[{current_section}] {' '.join(accumulated_words)}",
                start_time=float(section_idx),
                end_time=float(section_idx),
                token_count=len(accumulated_words),
            ))
        return chunks

    @staticmethod
    def _parse_srt(file_bytes: bytes) -> List[Chunk]:
        from backend.app.retrieval.transcript_loader import TranscriptLoader
        from backend.app.retrieval.chunker import TranscriptChunker
        content = file_bytes.decode("utf-8", errors="replace")
        loader = TranscriptLoader()
        segments = loader.parse_srt_text(content)
        chunker = TranscriptChunker()
        return chunker.chunk_segments(segments)

    @staticmethod
    def _parse_txt(file_bytes: bytes, chunk_size: int) -> List[Chunk]:
        content = file_bytes.decode("utf-8", errors="replace")
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        chunks = []
        idx = 1
        for p in paragraphs:
            words = p.split()
            for i in range(0, len(words), chunk_size):
                piece = " ".join(words[i:i + chunk_size])
                chunks.append(Chunk(
                    text=f"[Section {idx}] {piece}",
                    start_time=float(idx * 30),
                    end_time=float(idx * 30 + 30),
                    token_count=len(words[i:i + chunk_size]),
                ))
                idx += 1
        return chunks
