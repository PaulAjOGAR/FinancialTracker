from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

def generate_pdf(filename, content_list):
    styles = getSampleStyleSheet()
    pdf = SimpleDocTemplate(filename, pagesize=A4)
    story = []

    for text in content_list:
        story.append(Paragraph(text, styles["Normal"]))
        story.append(Spacer(1, 12))  # small spacing

    pdf.build(story)
    print(f"PDF saved as {filename}")
