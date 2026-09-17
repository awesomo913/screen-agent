"""
toolkit_32_pdf_tools.py
Work with PDF files: extract text, count pages, merge, split, rotate,
and get metadata. Uses PyMuPDF (fitz) or pdfplumber with soft-import fallbacks.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from PyPDF2 import PdfReader, PdfWriter, PdfMerger
    HAS_PYPDF2 = True
except ImportError:
    try:
        from pypdf import PdfReader, PdfWriter, PdfMerger
        HAS_PYPDF2 = True
    except ImportError:
        HAS_PYPDF2 = False

def check_libraries() -> Dict[str, Any]:
    return {"success": True, "data": {"fitz": HAS_FITZ, "pdfplumber": HAS_PDFPLUMBER, "pypdf": HAS_PYPDF2}, "error": None}

def get_pdf_info(path: str) -> Dict[str, Any]:
    try:
        if HAS_FITZ:
            doc = fitz.open(path)
            meta = doc.metadata
            info = {
                "path": path,
                "page_count": doc.page_count,
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "creator": meta.get("creator", ""),
                "producer": meta.get("producer", ""),
                "created": meta.get("creationDate", ""),
                "modified": meta.get("modDate", ""),
                "encrypted": doc.is_encrypted,
                "size_kb": round(os.path.getsize(path) / 1024, 1)
            }
            doc.close()
            return {"success": True, "data": info, "error": None}
        if HAS_PYPDF2:
            reader = PdfReader(path)
            meta = reader.metadata or {}
            return {"success": True, "data": {
                "path": path,
                "page_count": len(reader.pages),
                "title": str(meta.get("/Title", "")),
                "author": str(meta.get("/Author", "")),
                "size_kb": round(os.path.getsize(path) / 1024, 1)
            }, "error": None}
        return {"success": False, "data": None, "error": "No PDF library installed (install pymupdf or pypdf)"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def get_page_count(path: str) -> Dict[str, Any]:
    try:
        if HAS_FITZ:
            doc = fitz.open(path)
            count = doc.page_count
            doc.close()
            return {"success": True, "data": count, "error": None}
        if HAS_PYPDF2:
            reader = PdfReader(path)
            return {"success": True, "data": len(reader.pages), "error": None}
        return {"success": False, "data": None, "error": "No PDF library"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_text(path: str, start_page: int = 0, end_page: int = -1) -> Dict[str, Any]:
    try:
        if HAS_FITZ:
            doc = fitz.open(path)
            pages = list(range(doc.page_count))
            if end_page < 0:
                end_page = doc.page_count
            selected = pages[start_page:end_page]
            text = ""
            for i in selected:
                text += doc[i].get_text()
            doc.close()
            return {"success": True, "data": {"text": text, "chars": len(text), "pages": len(selected)}, "error": None}
        if HAS_PDFPLUMBER:
            with pdfplumber.open(path) as pdf:
                end = len(pdf.pages) if end_page < 0 else end_page
                text = "".join(p.extract_text() or "" for p in pdf.pages[start_page:end])
            return {"success": True, "data": {"text": text, "chars": len(text)}, "error": None}
        if HAS_PYPDF2:
            reader = PdfReader(path)
            end = len(reader.pages) if end_page < 0 else end_page
            text = "".join(reader.pages[i].extract_text() or "" for i in range(start_page, end))
            return {"success": True, "data": {"text": text, "chars": len(text)}, "error": None}
        return {"success": False, "data": None, "error": "No PDF library installed"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def extract_page_text(path: str, page_number: int = 0) -> Dict[str, Any]:
    try:
        if HAS_FITZ:
            doc = fitz.open(path)
            text = doc[page_number].get_text()
            doc.close()
            return {"success": True, "data": text, "error": None}
        if HAS_PYPDF2:
            reader = PdfReader(path)
            text = reader.pages[page_number].extract_text()
            return {"success": True, "data": text, "error": None}
        return {"success": False, "data": None, "error": "No PDF library"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def merge_pdfs(input_paths: list, output_path: str) -> Dict[str, Any]:
    try:
        if HAS_FITZ:
            merged = fitz.open()
            for p in input_paths:
                doc = fitz.open(p)
                merged.insert_pdf(doc)
                doc.close()
            merged.save(output_path)
            merged.close()
            return {"success": True, "data": {"saved": output_path, "merged": len(input_paths)}, "error": None}
        if HAS_PYPDF2:
            merger = PdfMerger()
            for p in input_paths:
                merger.append(p)
            merger.write(output_path)
            merger.close()
            return {"success": True, "data": {"saved": output_path, "merged": len(input_paths)}, "error": None}
        return {"success": False, "data": None, "error": "No PDF library"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def split_pdf(path: str, output_folder: str, pages_per_file: int = 1) -> Dict[str, Any]:
    try:
        if not HAS_FITZ and not HAS_PYPDF2:
            return {"success": False, "data": None, "error": "No PDF library"}
        os.makedirs(output_folder, exist_ok=True)
        stem = Path(path).stem
        if HAS_FITZ:
            doc = fitz.open(path)
            total = doc.page_count
            files = []
            for i in range(0, total, pages_per_file):
                sub = fitz.open()
                sub.insert_pdf(doc, from_page=i, to_page=min(i + pages_per_file - 1, total - 1))
                out = os.path.join(output_folder, stem + "_part" + str(i // pages_per_file + 1) + ".pdf")
                sub.save(out)
                sub.close()
                files.append(out)
            doc.close()
            return {"success": True, "data": {"files": files, "count": len(files)}, "error": None}
        return {"success": False, "data": None, "error": "fitz required for split"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def rotate_pdf(path: str, output_path: str, degrees: int = 90, page_index: int = -1) -> Dict[str, Any]:
    """Rotate one or all pages. page_index=-1 means all pages."""
    try:
        if HAS_FITZ:
            doc = fitz.open(path)
            pages = range(doc.page_count) if page_index < 0 else [page_index]
            for i in pages:
                doc[i].set_rotation((doc[i].rotation + degrees) % 360)
            doc.save(output_path)
            doc.close()
            return {"success": True, "data": {"saved": output_path, "rotated_pages": len(list(pages))}, "error": None}
        return {"success": False, "data": None, "error": "fitz (PyMuPDF) required"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def pdf_to_images(path: str, output_folder: str, dpi: int = 150, format: str = "png") -> Dict[str, Any]:
    try:
        if not HAS_FITZ:
            return {"success": False, "data": None, "error": "fitz (PyMuPDF) required"}
        os.makedirs(output_folder, exist_ok=True)
        doc = fitz.open(path)
        files = []
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(matrix=mat)
            out = os.path.join(output_folder, "page_" + str(i + 1) + "." + format)
            pix.save(out)
            files.append(out)
        doc.close()
        return {"success": True, "data": {"pages": len(files), "files": files}, "error": None}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}

def search_pdf(path: str, query: str) -> Dict[str, Any]:
    """Find pages containing a search term."""
    try:
        if HAS_FITZ:
            doc = fitz.open(path)
            matches = []
            for i in range(doc.page_count):
                found = doc[i].search_for(query)
                if found:
                    matches.append({"page": i, "occurrences": len(found)})
            doc.close()
            return {"success": True, "data": {"query": query, "pages_with_match": matches, "total_matches": sum(m["occurrences"] for m in matches)}, "error": None}
        return {"success": False, "data": None, "error": "fitz (PyMuPDF) required"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
