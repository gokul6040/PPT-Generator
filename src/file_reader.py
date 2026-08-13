"""Extract plain text from uploaded files: .txt, .docx, .pdf, .pptx."""
import io


def read_uploaded_file(uploaded_file) -> str:
    """
    Accept a Streamlit UploadedFile and return extracted text.
    Raises ValueError for unsupported types.
    """
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()

    if name.endswith(".txt"):
        return _read_txt(raw)
    elif name.endswith(".docx"):
        return _read_docx(raw)
    elif name.endswith(".pdf"):
        return _read_pdf(raw)
    elif name.endswith(".pptx"):
        return _read_pptx(raw)
    else:
        raise ValueError(
            f"Unsupported file type: '{uploaded_file.name}'. "
            "Please upload a .txt, .docx, .pdf, or .pptx file."
        )


def _read_txt(raw: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode text file. Please save it as UTF-8.")


def _read_docx(raw: bytes) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx is not installed. Run: pip install python-docx")

    doc = Document(io.BytesIO(raw))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        raise ValueError("The Word document appears to be empty or has no readable text.")
    return "\n".join(paragraphs)


def _read_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("pypdf is not installed. Run: pip install pypdf")

    reader = PdfReader(io.BytesIO(raw))
    pages_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text.strip())

    if not pages_text:
        raise ValueError("Could not extract text from the PDF. It may be image-based or encrypted.")

    return "\n\n".join(pages_text)


def _read_pptx(raw: bytes) -> str:
    try:
        from pptx import Presentation
    except ImportError:
        raise ImportError("python-pptx is not installed. Run: pip install python-pptx")

    prs = Presentation(io.BytesIO(raw))
    slide_texts = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = para.text.strip()
                    if line:
                        texts.append(line)
        if texts:
            slide_texts.append(f"[Slide {i}]\n" + "\n".join(texts))

    if not slide_texts:
        raise ValueError("The PowerPoint file has no readable text content.")

    return "\n\n".join(slide_texts)
