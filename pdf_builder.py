"""
pdf_builder.py — Builds a formatted .pdf from tailored resume data.
Returns bytes ready for storage/download.
"""

from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer


def _text(value):
    return (value or "").strip()


def build(resume_data: dict, job_title: str, company: str) -> bytes:
    """Build and return PDF bytes from resume_data dict."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()
    h_name = ParagraphStyle(
        "Name",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor("#1F3864"),
        alignment=1,
        spaceAfter=4,
    )
    h_headline = ParagraphStyle(
        "Headline",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        textColor=colors.HexColor("#2E74B5"),
        alignment=1,
        spaceAfter=2,
    )
    h_contact = ParagraphStyle(
        "Contact",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        alignment=1,
        spaceAfter=8,
    )
    h_section = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.HexColor("#2E74B5"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=2,
    )
    body_small = ParagraphStyle(
        "BodySmall",
        parent=body,
        fontSize=9.5,
        textColor=colors.HexColor("#666666"),
    )

    story = []

    name = _text(resume_data.get("name")) or "Candidate"
    headline = _text(resume_data.get("headline"))
    contact = _text(resume_data.get("contact"))

    story.append(Paragraph(name, h_name))
    if headline:
        story.append(Paragraph(headline, h_headline))
    if contact:
        story.append(Paragraph(contact, h_contact))
    story.append(Spacer(1, 4))

    summary = _text(resume_data.get("summary"))
    if summary:
        story.append(Paragraph("PROFESSIONAL SUMMARY", h_section))
        story.append(Paragraph(summary, body))

    skills = resume_data.get("skills") or {}
    story.append(Paragraph("TECHNICAL SKILLS", h_section))
    if isinstance(skills, dict):
        core = _text(skills.get("core"))
        if core:
            story.append(Paragraph(core, body))
        else:
            for label, value in skills.items():
                clean = _text(value)
                if clean:
                    story.append(Paragraph(f"<b>{label.replace('_', ' ').title()}:</b> {clean}", body))

    experience = resume_data.get("experience") or []
    if experience:
        story.append(Paragraph("PROFESSIONAL EXPERIENCE", h_section))
        for exp in experience:
            company_name = _text(exp.get("company"))
            role_title = _text(exp.get("title"))
            date_range = _text(exp.get("dates"))
            header_bits = [v for v in [company_name, role_title] if v]
            header = " — ".join(header_bits) if header_bits else "Experience"
            if date_range:
                header = f"{header} ({date_range})"
            story.append(Paragraph(f"<b>{header}</b>", body))

            bullets = exp.get("bullets") or []
            if bullets:
                items = [
                    ListItem(Paragraph(_text(b), body), leftIndent=10)
                    for b in bullets
                    if _text(b)
                ]
                if items:
                    story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
                    story.append(Spacer(1, 2))

    education = resume_data.get("education") or []
    if education:
        story.append(Paragraph("EDUCATION", h_section))
        for item in education:
            clean = _text(item)
            if clean:
                story.append(Paragraph(clean, body))

    certifications = resume_data.get("certifications") or []
    if certifications:
        story.append(Paragraph("CERTIFICATIONS", h_section))
        certs_text = " • ".join([_text(c) for c in certifications if _text(c)])
        if certs_text:
            story.append(Paragraph(certs_text, body_small))

    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Tailored for {job_title} at {company}", body_small))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
