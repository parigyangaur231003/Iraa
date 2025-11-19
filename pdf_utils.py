from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import fonts
import os


def generate_pdf(text: str, out_path: str) -> str:
    """Generate a simple PDF from plain text at the given path.
    Ensures directory exists, uses basic wrapping, and UTF-8 safe rendering.
    Returns the absolute output path.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Configure a basic document
    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="Iraa Document",
        author="Iraa",
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        alignment=TA_LEFT,
    )

    # Convert plain text with newlines into Paragraphs with line breaks
    paragraphs = []
    for line in text.split("\n"):
        if line.strip() == "":
            paragraphs.append(Spacer(1, 6))
        else:
            paragraphs.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), body_style))
            paragraphs.append(Spacer(1, 4))

    doc.build(paragraphs)
    return os.path.abspath(out_path)
