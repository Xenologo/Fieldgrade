from __future__ import annotations
import mimetypes
from pathlib import Path
from typing import Optional, Tuple

def sniff_mime(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    return mt or "application/octet-stream"

def extract_text_best_effort(path: Path, raw_bytes: bytes) -> Tuple[Optional[str], str]:
    mime = sniff_mime(path)
    suffix = path.suffix.lower()

    if mime.startswith("text/") or suffix in {".md",".txt",".log",".json",".yaml",".yml",".py",".js",".ts",".html",".css"}:
        try:
            return raw_bytes.decode("utf-8"), "utf8"
        except UnicodeDecodeError:
            try:
                return raw_bytes.decode("latin-1"), "latin1"
            except Exception:
                return None, "none"

    if suffix == ".pdf" or mime == "application/pdf":
        try:
            from pypdf import PdfReader  # type: ignore
            import io
            reader = PdfReader(io.BytesIO(raw_bytes))
            parts = []
            for page in reader.pages:
                t = page.extract_text() or ""
                if t:
                    parts.append(t)
            text = "\n\n".join(parts).strip()
            return (text if text else None), "pypdf"
        except Exception:
            return None, "none"

    if suffix == ".docx":
        try:
            import io
            from docx import Document  # type: ignore
            doc = Document(io.BytesIO(raw_bytes))
            parts = [p.text for p in doc.paragraphs if p.text]
            text = "\n".join(parts).strip()
            return (text if text else None), "docx"
        except Exception:
            return None, "none"

    return None, "none"
