"""
services/pdf_service.py
------------------------
Extracts raw text from an uploaded PDF so it can be fed into the
LangGraph `parse_input_node`. Kept as its own service module so the
extraction strategy (pdfplumber today) can be swapped later without
touching router/graph code.
"""

import io
import pdfplumber


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract and concatenate text from every page of a PDF's bytes."""
    text_chunks = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_chunks.append(page_text)

    if not text_chunks:
        raise ValueError("No extractable text found in PDF (it may be a scanned image).")

    return "\n".join(text_chunks)
