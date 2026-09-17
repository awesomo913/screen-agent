# pdf_actions.py
"""Utility functions for PDF manipulation used by the Screen‑Agent Toolkit."""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import fitz  # PyMuPDF
import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# --------------------------------------------------------------------------- #
# Helper --------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def _make_response(success: bool, data: Any = None, message: str = "") -> Dict[str, Any]:
    """Standardised response dictionary."""
    return {"success": success, "data": data, "message": message}


def _ensure_path(p: Union[str, Path]) -> Path:
    """Convert to Path and make parent directories if needed."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# --------------------------------------------------------------------------- #
# 1. Read PDF text ---------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def read_pdf_text(filepath: Union[str, Path], pages: Union[List[int], None] = None) -> Dict[str, Any]:
    """
    Extract plain text from *pages* of *filepath*.
    If ``pages`` is ``None`` all pages are read.
    """
    try:
        path = _ensure_path(filepath)
        reader = PdfReader(str(path))
        n_pages = len(reader.pages)

        if pages is None:
            pages = list(range(n_pages))
        else:
            # normalise negative indices and remove out‑of‑range values
            pages = [p if p >= 0 else n_pages + p for p in pages]
            pages = [p for p in pages if 0 <= p < n_pages]

        extracted = "\n".join(reader.pages[p].extract_text() or "" for p in pages)
        return _make_response(True, {"text": extracted}, f"Extracted text from {len(pages)} page(s).")
    except Exception as exc:
        return _make_response(False, None, f"Failed to read PDF text: {exc}")


# --------------------------------------------------------------------------- #
# 2. Extract PDF metadata ---------------------------------------------------- #
# --------------------------------------------------------------------------- #

def extract_pdf_metadata(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Return the metadata dictionary of *filepath*."""
    try:
        path = _ensure_path(filepath)
        reader = PdfReader(str(path))
        meta = {k: v for k, v in reader.metadata.items()}  # type: ignore[arg-type]
        return _make_response(True, {"metadata": meta}, "Metadata extracted.")
    except Exception as exc:
        return _make_response(False, None, f"Metadata extraction failed: {exc}")


# --------------------------------------------------------------------------- #
# 3. Merge PDFs ------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def merge_pdfs(file_list: List[Union[str, Path]], output: Union[str, Path]) -> Dict[str, Any]:
    """
    Merge PDFs in ``file_list`` (order kept) into ``output``.
    """
    try:
        writer = PdfWriter()
        for f in file_list:
            path = _ensure_path(f)
            reader = PdfReader(str(path))
            for page in reader.pages:
                writer.add_page(page)

        out_path = _ensure_path(output)
        with out_path.open("wb") as f_out:
            writer.write(f_out)

        return _make_response(True, {"output": str(out_path)}, f"Merged {len(file_list)} PDFs.")
    except Exception as exc:
        return _make_response(False, None, f"PDF merge failed: {exc}")


# --------------------------------------------------------------------------- #
# 4. Split PDF -------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def split_pdf(filepath: Union[str, Path], page_ranges: List[Tuple[int, int]], output_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Split ``filepath`` into several PDFs defined by ``page_ranges``.
    ``page_ranges`` is a list of ``(start, end)`` (0‑based inclusive) tuples.
    Files are written to ``output_dir`` with names ``original_001.pdf`` etc.
    """
    try:
        src_path = _ensure_path(filepath)
        out_dir = _ensure_path(output_dir)
        reader = PdfReader(str(src_path))

        created_files = []
        for i, (start, end) in enumerate(page_ranges, 1):
            writer = PdfWriter()
            for p in range(start, min(end + 1, len(reader.pages))):
                writer.add_page(reader.pages[p])

            out_name = out_dir / f"{src_path.stem}_{i:03}.pdf"
            with out_name.open("wb") as f_out:
                writer.write(f_out)
            created_files.append(str(out_name))

        return _make_response(True, {"files": created_files},
                              f"Created {len(created_files)} split PDFs.")
    except Exception as exc:
        return _make_response(False, None, f"PDF split failed: {exc}")


# --------------------------------------------------------------------------- #
# 5. Rotate PDF pages ------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def rotate_pdf_pages(filepath: Union[str, Path], angle: int, pages: Union[List[int], None] = None) -> Dict[str, Any]:
    """
    Rotate selected *pages* by *angle* degrees clockwise.
    If ``pages`` is ``None`` rotate all pages.
    """
    try:
        src_path = _ensure_path(filepath)
        reader = PdfReader(str(src_path))
        writer = PdfWriter()

        n_pages = len(reader.pages)
        if pages is None:
            pages = list(range(n_pages))
        else:
            pages = [p if p >= 0 else n_pages + p for p in pages]
            pages = [p for p in pages if 0 <= p < n_pages]

        for i, page in enumerate(reader.pages):
            if i in pages:
                page.rotate_clockwise(angle % 360)
            writer.add_page(page)

        out_path = src_path.parent / f"{src_path.stem}_rotated.pdf"
        with out_path.open("wb") as f_out:
            writer.write(f_out)

        return _make_response(True, {"output": str(out_path)},
                              f"Rotated {len(pages)} page(s).")
    except Exception as exc:
        return _make_response(False, None, f"Rotation failed: {exc}")


# --------------------------------------------------------------------------- #
# 6. Add Watermark ----------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def _make_watermark_pdf(text: str, page_size: Tuple[float, float]) -> bytes:
    """Create a one‑page PDF containing *text* centred, used as a watermark."""
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=page_size)
    c.setFillAlpha(0.15)
    c.setFont("Helvetica", 72)
    c.saveState()
    c.translate(page_size[0] / 2, page_size[1] / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.save()
    packet.seek(0)
    return packet.read()


def add_watermark(filepath: Union[str, Path], watermark_text: str, output: Union[str, Path]) -> Dict[str, Any]:
    """
    Overlay *watermark_text* on every page of *filepath*.
    The watermark is semi‑transparent and diagonal.
    """
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        reader = PdfReader(str(src_path))
        writer = PdfWriter()

        # Create a single‑page watermark PDF in memory
        first_page = reader.pages[0]
        wm_bytes = _make_watermark_pdf(watermark_text, first_page.mediabox.upper_right)
        wm_reader = PdfReader(io.BytesIO(wm_bytes))
        watermark_page = wm_reader.pages[0]

        for page in reader.pages:
            page.merge_page(watermark_page)
            writer.add_page(page)

        with out_path.open("wb") as f_out:
            writer.write(f_out)

        return _make_response(True, {"output": str(out_path)},
                              "Watermark added.")
    except Exception as exc:
        return _make_response(False, None, f"Watermarking failed: {exc}")


# --------------------------------------------------------------------------- #
# 7. Encrypt / Decrypt ------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def encrypt_pdf(filepath: Union[str, Path], password: str, output: Union[str, Path]) -> Dict[str, Any]:
    """Encrypt *filepath* with *password* and write to *output*."""
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        reader = PdfReader(str(src_path))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(user_password=password, owner_password=None, use_128bit=True)

        with out_path.open("wb") as f_out:
            writer.write(f_out)

        return _make_response(True, {"output": str(out_path)}, "PDF encrypted.")
    except Exception as exc:
        return _make_response(False, None, f"Encryption failed: {exc}")


def decrypt_pdf(filepath: Union[str, Path], password: str, output: Union[str, Path]) -> Dict[str, Any]:
    """Decrypt *filepath* using *password* and write the clear PDF to *output*."""
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        reader = PdfReader(str(src_path))
        if reader.is_encrypted:
            reader.decrypt(password)

        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        with out_path.open("wb") as f_out:
            writer.write(f_out)

        return _make_response(True, {"output": str(out_path)}, "PDF decrypted.")
    except Exception as exc:
        return _make_response(False, None, f"Decryption failed: {exc}")


# --------------------------------------------------------------------------- #
# 8. PDF → Images ------------------------------------------------------------ #
# --------------------------------------------------------------------------- #

def pdf_to_images(filepath: Union[str, Path], output_dir: Union[str, Path], dpi: int = 150) -> Dict[str, Any]:
    """
    Render every page of *filepath* as a PNG image in *output_dir*.
    Returns list of generated image file paths.
    """
    try:
        src_path = _ensure_path(filepath)
        out_dir = _ensure_path(output_dir)

        doc = fitz.open(str(src_path))
        images = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi)
            img_path = out_dir / f"{src_path.stem}_page_{page_num + 1}.png"
            pix.save(str(img_path))
            images.append(str(img_path))

        return _make_response(True, {"images": images}, f"Rendered {len(images)} page(s).")
    except Exception as exc:
        return _make_response(False, None, f"PDF → images failed: {exc}")


# --------------------------------------------------------------------------- #
# 9. Images → PDF ------------------------------------------------------------ #
# --------------------------------------------------------------------------- #

def images_to_pdf(image_paths: List[Union[str, Path]], output: Union[str, Path]) -> Dict[str, Any]:
    """Create a PDF from a list of images (ordered)."""
    try:
        out_path = _ensure_path(output)
        c = canvas.Canvas(str(out_path), pagesize=letter)

        for img_path in image_paths:
            img_path = Path(img_path)
            if not img_path.is_file():
                continue

            # Fit image to page while preserving aspect ratio
            img = fitz.open(str(img_path))
            rect = img[0].rect
            width = rect.width
            height = rect.height
            max_w, max_h = letter

            scale = min(max_w / width, max_h / height)
            w, h = width * scale, height * scale
            x = (max_w - w) / 2
            y = (max_h - h) / 2

            c.drawImage(str(img_path), x, y, w, h)
            c.showPage()
            img.close()

        c.save()
        return _make_response(True, {"output": str(out_path)}, f"Created PDF from {len(image_paths)} image(s).")
    except Exception as exc:
        return _make_response(False, None, f"Images → PDF failed: {exc}")


# --------------------------------------------------------------------------- #
# 10. Extract tables (rudimentary) ------------------------------------------ #
# --------------------------------------------------------------------------- #

def extract_pdf_tables(filepath: Union[str, Path], pages: Union[List[int], None] = None) -> Dict[str, Any]:
    """
    Very light‑weight table extraction – returns each page's raw text.
    (Full‑blown table extraction would require additional heavy dependencies
    like `tabula-py` or `camelot`, which are out of scope for this toolkit.)
    """
    try:
        txt_res = read_pdf_text(filepath, pages)
        if not txt_res["success"]:
            return txt_res
        text = txt_res["data"]["text"]
        tables = []  # Placeholder – user can post‑process the text.
        return _make_response(True, {"tables_raw_text": text, "tables": tables},
                              "Extracted raw text for manual table parsing.")
    except Exception as exc:
        return _make_response(False, None, f"Table extraction failed: {exc}")


# --------------------------------------------------------------------------- #
# 11. Add page numbers ------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def add_page_numbers(filepath: Union[str, Path], output: Union[str, Path],
                    position: Tuple[float, float] = (0.5 * inch, 0.5 * inch)) -> Dict[str, Any]:
    """
    Overlay simple page numbers (bottom‑left by default) onto each page.
    ``position`` is expressed in points from the lower‑left corner.
    """
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        reader = PdfReader(str(src_path))
        writer = PdfWriter()

        for i, page in enumerate(reader.pages, 1):
            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=page.mediabox.upper_right)
            c.setFont("Helvetica", 9)
            x, y = position
            c.drawString(x, y, str(i))
            c.save()
            packet.seek(0)

            overlay = PdfReader(packet).pages[0]
            page.merge_page(overlay)
            writer.add_page(page)

        with out_path.open("wb") as f_out:
            writer.write(f_out)

        return _make_response(True, {"output": str(out_path)}, "Page numbers added.")
    except Exception as exc:
        return _make_response(False, None, f"Adding page numbers failed: {exc}")


# --------------------------------------------------------------------------- #
# 12. Compress PDF ----------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def compress_pdf(filepath: Union[str, Path], output: Union[str, Path]) -> Dict[str, Any]:
    """
    Compress *filepath* using PyMuPDF's ``save(..., garbage=True, deflate=True)``.
    """
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        doc = fitz.open(str(src_path))
        doc.save(str(out_path), garbage=True, deflate=True)
        doc.close()
        return _make_response(True, {"output": str(out_path)},
                              "PDF compressed using MuPDF.")
    except Exception as exc:
        return _make_response(False, None, f"Compression failed: {exc}")


# --------------------------------------------------------------------------- #
# 13. Extract images --------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def extract_pdf_images(filepath: Union[str, Path], output_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Export all images embedded in *filepath* into *output_dir*.
    Returns list of saved image file paths.
    """
    try:
        src_path = _ensure_path(filepath)
        out_dir = _ensure_path(output_dir)

        doc = fitz.open(str(src_path))
        saved = []
        for page_number in range(doc.page_count):
            page = doc.load_page(page_number)
            imglist = page.get_images(full=True)

            for img_index, img in enumerate(imglist, 1):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.n < 5:       # this is GRAY or RGB
                    pix.save(str(out_dir / f"{src_path.stem}_p{page_number + 1}_i{img_index}.png"))
                else:               # CMYK: convert to PNG by removing alpha
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                    pix.save(str(out_dir / f"{src_path.stem}_p{page_number + 1}_i{img_index}.png"))
                saved.append(str(out_dir / f"{src_path.stem}_p{page_number + 1}_i{img_index}.png"))
                pix = None  # free memory
        doc.close()
        return _make_response(True, {"images": saved},
                              f"Extracted {len(saved)} image(s).")
    except Exception as exc:
        return _make_response(False, None, f"Image extraction failed: {exc}")


# --------------------------------------------------------------------------- #
# 14. Create PDF from plain text -------------------------------------------- #
# --------------------------------------------------------------------------- #

def create_pdf_from_text(text: str, output: Union[str, Path], font_size: int = 12) -> Dict[str, Any]:
    """Generate a single‑page PDF with *text* using ReportLab."""
    try:
        out_path = _ensure_path(output)
        c = canvas.Canvas(str(out_path), pagesize=letter)
        width, height = letter
        text_obj = c.beginText(inch, height - inch)
        text_obj.setFont("Helvetica", font_size)
        for line in text.splitlines():
            text_obj.textLine(line)
        c.drawText(text_obj)
        c.save()
        return _make_response(True, {"output": str(out_path)}, "PDF created from text.")
    except Exception as exc:
        return _make_response(False, None, f"Creating PDF from text failed: {exc}")


# --------------------------------------------------------------------------- #
# 15. Add PDF bookmarks ------------------------------------------------------ #
# --------------------------------------------------------------------------- #

def add_pdf_bookmark(filepath: Union[str, Path],
                    bookmarks: List[Tuple[str, int]],
                    output: Union[str, Path]) -> Dict[str, Any]:
    """
    Add hierarchical bookmarks.
    ``bookmarks`` – list of ``(title, page_number)`` tuples (0‑based page index).
    """
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        reader = PdfReader(str(src_path))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # add bookmarks (top‑level only for simplicity)
        for title, page_idx in bookmarks:
            if 0 <= page_idx < len(reader.pages):
                writer.add_bookmark(title, page_idx)

        with out_path.open("wb") as f_out:
            writer.write(f_out)

        return _make_response(True, {"output": str(out_path)},
                              f"Added {len(bookmarks)} bookmark(s).")
    except Exception as exc:
        return _make_response(False, None, f"Bookmarking failed: {exc}")


# --------------------------------------------------------------------------- #
# 16. Search PDF text -------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def search_pdf_text(filepath: Union[str, Path], pattern: str) -> Dict[str, Any]:
    """
    Search *pattern* (regular expression) in the entire PDF.
    Returns list of ``(page_number, match_text)``.
    """
    try:
        txt_res = read_pdf_text(filepath, None)
        if not txt_res["success"]:
            return txt_res

        full_text = txt_res["data"]["text"]
        comp = re.compile(pattern, re.MULTILINE)
        matches = [(m.start(), m.group()) for m in comp.finditer(full_text)]
        return _make_response(True, {"matches": matches},
                              f"Found {len(matches)} match(es).")
    except Exception as exc:
        return _make_response(False, None, f"Search failed: {exc}")


# --------------------------------------------------------------------------- #
# 17. Highlight PDF text ---------------------------------------------------- #
# --------------------------------------------------------------------------- #

def highlight_pdf_text(filepath: Union[str, Path], search_term: str, output: Union[str, Path]) -> Dict[str, Any]:
    """
    Add yellow highlight annotations for every occurrence of *search_term*.
    Simple case‑insensitive search.
    """
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        doc = fitz.open(str(src_path))
        total = 0
        for page in doc:
            text_instances = page.search_for(search_term, hit_max=0)
            for inst in text_instances:
                highlight = page.add_highlight_annot(inst)
                highlight.set_colors(stroke=colors.yellow, fill=colors.yellow)  # type: ignore[arg-type]
                highlight.update()
                total += 1
        doc.save(str(out_path), garbage=True, deflate=True)
        doc.close()
        return _make_response(True, {"output": str(out_path), "highlights_added": total},
                              f"Added {total} highlight(s).")
    except Exception as exc:
        return _make_response(False, None, f"Highlighting failed: {exc}")


# --------------------------------------------------------------------------- #
# 18. Get PDF page count ----------------------------------------------------- #
# --------------------------------------------------------------------------- #

def get_pdf_page_count(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Return the number of pages in *filepath*."""
    try:
        src_path = _ensure_path(filepath)
        reader = PdfReader(str(src_path))
        count = len(reader.pages)
        return _make_response(True, {"page_count": count},
                              f"PDF has {count} page(s).")
    except Exception as exc:
        return _make_response(False, None, f"Page count failed: {exc}")


# --------------------------------------------------------------------------- #
# 19. Crop PDF pages -------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def crop_pdf_pages(filepath: Union[str, Path],
                  box: Tuple[float, float, float, float],
                  pages: Union[List[int], None],
                  output: Union[str, Path]) -> Dict[str, Any]:
    """
    Crop pages to ``box`` = (x0, y0, x1, y1) expressed in points.
    If ``pages`` is ``None`` all pages are cropped.
    """
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        reader = PdfReader(str(src_path))
        writer = PdfWriter()

        n_pages = len(reader.pages)
        if pages is None:
            pages = list(range(n_pages))
        else:
            pages = [p if p >= 0 else n_pages + p for p in pages]
            pages = [p for p in pages if 0 <= p < n_pages]

        for i, page in enumerate(reader.pages):
            if i in pages:
                page.mediabox.lower_left = (box[0], box[1])
                page.mediabox.upper_right = (box[2], box[3])
            writer.add_page(page)

        with out_path.open("wb") as f_out:
            writer.write(f_out)

        return _make_response(True, {"output": str(out_path)},
                              f"Cropped {len(pages)} page(s).")
    except Exception as exc:
        return _make_response(False, None, f"Cropping failed: {exc}")


# --------------------------------------------------------------------------- #
# 20. PDF → HTML ------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def pdf_to_html(filepath: Union[str, Path], output: Union[str, Path]) -> Dict[str, Any]:
    """
    Convert the whole PDF to a single HTML document using MuPDF's ``get_text("html")``.
    """
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        doc = fitz.open(str(src_path))
        html = ""
        for page in doc:
            html += page.get_text("html")
        doc.close()

        out_path.write_text(html, encoding="utf-8")
        return _make_response(True, {"output": str(out_path)},
                              "PDF converted to HTML.")
    except Exception as exc:
        return _make_response(False, None, f"PDF→HTML failed: {exc}")


# --------------------------------------------------------------------------- #
# 21. Stamp PDF (image) ------------------------------------------------------ #
# --------------------------------------------------------------------------- #

def stamp_pdf(filepath: Union[str, Path],
              stamp_image: Union[str, Path],
              position: Tuple[float, float] = (0, 0),
              output: Union[str, Path] = None) -> Dict[str, Any]:
    """
    Overlay *stamp_image* on each page at ``position`` (points from lower‑left).
    If ``output`` is ``None`` a ``*_stamped.pdf`` sibling is created.
    """
    try:
        src_path = _ensure_path(filepath)
        stamp_path = _ensure_path(stamp_image)
        out_path = _ensure_path(output) if output else src_path.parent / f"{src_path.stem}_stamped.pdf"

        reader = PdfReader(str(src_path))
        writer = PdfWriter()

        stamp_pdf_bytes = _image_to_pdf_page(str(stamp_path), position, reader.pages[0].mediabox.upper_right)
        stamp_reader = PdfReader(io.BytesIO(stamp_pdf_bytes))
        stamp_page = stamp_reader.pages[0]

        for page in reader.pages:
            page.merge_page(stamp_page)
            writer.add_page(page)

        with out_path.open("wb") as f_out:
            writer.write(f_out)

        return _make_response(True, {"output": str(out_path)},
                              "Stamp image applied.")
    except Exception as exc:
        return _make_response(False, None, f"Stamping failed: {exc}")


def _image_to_pdf_page(image_path: str,
                       position: Tuple[float, float],
                       page_size: Tuple[float, float]) -> bytes:
    """
    Produce a one‑page PDF (in memory) containing *image_path* placed at *position*.
    """
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=page_size)
    c.drawImage(image_path, position[0], position[1])
    c.save()
    packet.seek(0)
    return packet.read()


# --------------------------------------------------------------------------- #
# 22. Redact PDF text ------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def redact_pdf_text(filepath: Union[str, Path],
                    patterns: List[str],
                    output: Union[str, Path]) -> Dict[str, Any]:
    """
    Redact every occurrence of the regular‑expression strings in ``patterns``.
    The redaction is performed with black rectangles.
    """
    try:
        src_path = _ensure_path(filepath)
        out_path = _ensure_path(output)

        doc = fitz.open(str(src_path))
        total = 0
        for page in doc:
            for pat in patterns:
                rects = page.search_for(pat, hit_max=0)
                for rect in rects:
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    total += 1
            # Apply the redactions for the page
            page.apply_redactions()
        doc.save(str(out_path), garbage=True, deflate=True)
        doc.close()
        return _make_response(True, {"output": str(out_path), "redactions": total},
                              f"Applied {total} redaction(s).")
    except Exception as exc:
        return _make_response(False, None, f"Redaction failed: {exc}")


# --------------------------------------------------------------------------- #
# 23. Extract PDF links ------------------------------------------------------ #
# --------------------------------------------------------------------------- #

def extract_pdf_links(filepath: Union[str, Path]) -> Dict[str, Any]:
    """
    Return a list of dictionaries: ``{'page': int, 'uri': str, 'rect': (x0, y0, x1, y1)}``.
    """
    try:
        src_path = _ensure_path(filepath)
        doc = fitz.open(str(src_path))
        links = []
        for page_number, page in enumerate(doc, 1):
            for link in page.get_links():
                if link["uri"]:
                    links.append({
                        "page": page_number,
                        "uri": link["uri"],
                        "rect": tuple(link["from"]),
                    })
        doc.close()
        return _make_response(True, {"links": links},
                              f"Found {len(links)} link(s).")
    except Exception as exc:
        return _make_response(False, None, f"Link extraction failed: {exc}")


# --------------------------------------------------------------------------- #
# 24. Create PDF form -------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def create_pdf_form(fields: List[Dict[str, Any]], output: Union[str, Path]) -> Dict[str, Any]:
    """
    Build a simple AcroForm PDF.
    ``fields`` is a list of dicts, each containing:
        - ``type``: "text", "checkbox", "radio", "dropdown"
        - ``name``: field name (str)
        - ``x``, ``y``: position in points (lower‑left origin)
        - ``width``, ``height``: size in points
        - Optional extra keys depending on type (e.g. "options" for dropdown)
    """
    try:
        out_path = _ensure_path(output)
        c = canvas.Canvas(str(out_path), pagesize=letter)
        c.setFont("Helvetica", 12)

        for field in fields:
            f_type = field.get("type", "text")
            name = field.get("name", "field")
            x = float(field.get("x", inch))
            y = float(field.get("y", inch))
            w = float(field.get("width", 2 * inch))
            h = float(field.get("height", 0.3 * inch))

            if f_type == "text":
                c.acroForm.textfield(name=name, tooltip=name,
                                     x=x, y=y, width=w, height=h,
                                     borderStyle='solid', borderColor=colors.black,
                                     fillColor=colors.white, textColor=colors.black,
                                     forceBorder=True)
            elif f_type == "checkbox":
                c.acroForm.checkbox(name=name, tooltip=name,
                                    x=x, y=y, size=h,
                                    borderStyle='solid', borderColor=colors.black,
                                    fillColor=colors.white, textColor=colors.black,
                                    checked=False, forceBorder=True)
            elif f_type == "radio":
                options = field.get("options", [])
                for i, opt in enumerate(options):
                    c.acroForm.radio(name=name, tooltip=opt,
                                     value=opt, selected=False,
                                     x=x + i * (w + 5), y=y,
                                     size=h,
                                     borderStyle='solid', borderColor=colors.black,
                                     fillColor=colors.white, forceBorder=True)
            elif f_type == "dropdown":
                opts = field.get("options", [])
                c.acroForm.choice(name=name, tooltip=name,
                                 x=x, y=y, width=w, height=h,
                                 options=opts, value=opts[0] if opts else '',
                                 borderStyle='solid', borderColor=colors.black,
                                 fillColor=colors.white, textColor=colors.black,
                                 forceBorder=True)
            else:
                # Unsupported field type – ignore but keep PDF valid.
                c.drawString(x, y, f"[Unsupported field: {f_type}]")

        c.save()
        return _make_response(True, {"output": str(out_path)},
                              "PDF form created.")
    except Exception as exc:
        return _make_response(False, None, f"Form creation failed: {exc}")


# --------------------------------------------------------------------------- #
# End of module ------------------------------------------------------------- #
# --------------------------------------------------------------------------- #