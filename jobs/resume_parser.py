import re
from pathlib import Path
from PyPDF2 import PdfReader
from docx import Document


def extract_resume_text(file_path):
    """
    Extract text from PDF, DOCX, or TXT resume.
    """

    extension = Path(file_path).suffix.lower()

    # PDF
    if extension == '.pdf':
        reader = PdfReader(file_path)

        text = ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        return text

    # DOCX
    elif extension == '.docx':
        document = Document(file_path)

        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

        return text

    # TXT
    elif extension == '.txt':
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()

    else:
        return ""


def extract_email(text):

    match = re.search(
        r'[\w.-]+@[\w.-]+\.\w+',
        text
    )

    return match.group(0) if match else ''


def extract_candidate_name(text, fallback_filename=''):

    # Best-effort: assume the first non-empty line is the name
    for line in text.strip().split('\n'):

        line = line.strip()

        if line and len(line.split()) <= 5 and '@' not in line:
            return line

    # Fallback: use filename without extension
    return fallback_filename.rsplit(
        '.', 1
    )[0].replace('_', ' ').title()


def extract_experience_years(text):

    match = re.search(
        r'(\d+)\+?\s*years?',
        text,
        re.IGNORECASE
    )

    return int(match.group(1)) if match else 0


def extract_resume_info(file_path, filename=''):

    text = extract_resume_text(file_path)

    return {
    'resume_text': text,
    'candidate_name': extract_candidate_name(text, filename),
    'email': extract_email(text),
    'experience_years': extract_experience_years(text),
    'education_level': extract_education_level(text),
}
def extract_education_level(text):
    text = text.lower()
    if re.search(r'\b(ph\.?d|doctorate)\b', text):
        return 'PhD'
    if re.search(r'\b(m\.?c\.?a|m\.?tech|m\.?sc|masters?|post\s*grad)\b', text):
        return 'Masters'
    if re.search(r'\b(b\.?c\.?a|b\.?tech|b\.?sc|bachelors?|under\s*grad)\b', text):
        return 'Bachelors'
    if re.search(r'\bdiploma\b', text):
        return 'Diploma'
    return ''
