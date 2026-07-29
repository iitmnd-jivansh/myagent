"""
File processing utilities for multimodal chat support.
Handles images, PDFs, DOCX, and text files.
"""
import os
import base64
import tempfile
from pathlib import Path

def process_uploaded_file(file_path, filename):
    """
    Process an uploaded file and return extracted content.
    
    Returns:
        dict with keys:
            - type: "image" | "document" | "text"
            - content: base64 string for images, text string for documents
            - filename: original filename
            - description: human-readable description
    """
    ext = Path(filename).suffix.lower()
    
    # Image files
    if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
        return _process_image(file_path, filename)
    
    # PDF files
    if ext == '.pdf':
        return _process_pdf(file_path, filename)
    
    # Word documents
    if ext in ('.docx', '.doc'):
        return _process_docx(file_path, filename)
    
    # Text files
    if ext in ('.txt', '.csv', '.md', '.json', '.xml', '.yaml', '.yml'):
        return _process_text(file_path, filename)
    
    return {
        "type": "unknown",
        "content": None,
        "filename": filename,
        "description": f"Unsupported file type: {ext}"
    }


def _process_image(file_path, filename):
    """Read an image file and return base64 encoded content."""
    print(f"[FILE] Processing image: {filename}")
    with open(file_path, "rb") as f:
        image_data = f.read()
    
    image_b64 = base64.b64encode(image_data).decode("utf-8")
    
    ext = Path(filename).suffix.lower().lstrip('.')
    if ext == 'jpg':
        ext = 'jpeg'
    
    print(f"[FILE]   Image size: {len(image_data)} bytes, base64: {len(image_b64)} chars")
    
    return {
        "type": "image",
        "content": image_b64,
        "mime": f"image/{ext}",
        "filename": filename,
        "description": f"Image file: {filename}"
    }


def _process_pdf(file_path, filename):
    """Extract text from a PDF file."""
    print(f"[FILE] Processing PDF: {filename}")
    import fitz  # PyMuPDF
    
    text_parts = []
    doc = fitz.open(file_path)
    total_pages = len(doc)
    
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            text_parts.append(f"[Page {i+1}/{total_pages}]\n{text}")
    
    doc.close()
    full_text = "\n\n".join(text_parts)
    
    print(f"[FILE]   PDF pages: {total_pages}, extracted text: {len(full_text)} chars")
    
    return {
        "type": "document",
        "content": full_text,
        "filename": filename,
        "description": f"PDF document ({total_pages} pages): {filename}"
    }


def _process_docx(file_path, filename):
    """Extract text from a DOCX file."""
    print(f"[FILE] Processing DOCX: {filename}")
    import docx
    
    doc = docx.Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)
    
    print(f"[FILE]   DOCX paragraphs: {len(paragraphs)}, extracted text: {len(full_text)} chars")
    
    return {
        "type": "document",
        "content": full_text,
        "filename": filename,
        "description": f"Word document: {filename}"
    }


def _process_text(file_path, filename):
    """Read a plain text file."""
    print(f"[FILE] Processing text file: {filename}")
    
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    print(f"[FILE]   Text file size: {len(content)} chars")
    
    return {
        "type": "document",
        "content": content,
        "filename": filename,
        "description": f"Text file: {filename}"
    }