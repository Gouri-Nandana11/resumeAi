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


# Words that mean "this line is a heading / contact / place, not a person's name"
NAME_STOPWORDS = {
    'resume', 'curriculum', 'vitae', 'cv', 'summary', 'objective', 'profile', 'education',
    'experience', 'skills', 'projects', 'project', 'declaration', 'contact', 'address', 'phone',
    'mobile', 'email', 'linkedin', 'github', 'portfolio', 'college', 'university', 'institute',
    'school', 'department', 'engineering', 'technology', 'report', 'message', 'messages', 'inbox',
    'gmail', 'page', 'certifications', 'achievements', 'references', 'about', 'career',
    'personal', 'details', 'profit', 'loss', 'batch',
    'dear', 'hello', 'hi', 'regards', 'thanks', 'subject', 'from', 'to',
}

# Icon labels that PDF text extraction leaves next to contact details ("... Envelope", "Map-marker-alt")
ICON_WORDS = r'\b(envelope|map-marker-alt|linkedin|github|phone|mobile|call|location|email|e-mail|address)\b'


def _name_from_line(line):
    """Strip emails, links, phone numbers and icon labels; keep the line only if it looks like a name."""
    line = re.sub(r'[\w.+-]+@[\w-]+(\.[\w-]+)+', ' ', line)                      # emails
    line = re.sub(r'(https?://|www\.)\S+', ' ', line, flags=re.I)                  # links
    line = re.sub(r'\b[\w.-]+\.(com|in|org|net|io)\S*', ' ', line, flags=re.I)     # linkedin.com/in/...
    line = re.sub(r'\+?\d[\d\s()\-]{6,}\d', ' ', line)                           # phone numbers
    line = re.sub(ICON_WORDS, ' ', line, flags=re.I)
    line = re.sub(r'[|\u2022\u00b7,;:/\\]+', ' ', line)
    words = line.split()

    if not 2 <= len(words) <= 4:
        return ''
    for w in words:
        if not re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", w):
            return ''
        if w.lower().strip('.') in NAME_STOPWORDS:
            return ''
    return ' '.join(w.capitalize() if (w.isupper() or w.islower()) else w for w in words)


def _name_from_email(email):
    local = email.split('@')[0] if email else ''
    parts = [p for p in re.split(r'[._\-]+', re.sub(r'\d+', '', local)) if len(p) > 1]
    return ' '.join(p.capitalize() for p in parts) if len(parts) >= 2 else ''


def _name_from_filename(filename):
    stem = filename.rsplit('.', 1)[0]
    stem = re.sub(r'_[A-Za-z0-9]{7}$', '', stem)                 # suffix Django adds to duplicate file names
    stem = re.sub(r'[_\-.\d]+', ' ', stem)
    stem = re.sub(r'\b(resume|cv|curriculum|vitae|final|copy|updated|new)\b', ' ', stem, flags=re.I)
    stem = ' '.join(stem.split())
    # a long leftover is a document title, not a person's name
    return stem.title() if re.search(r'[A-Za-z]{2}', stem) and len(stem.split()) <= 4 else ''


def extract_candidate_name(text, fallback_filename=''):
    """Name from the first lines of the resume; falls back to the email, then the file name."""
    lines = [l.strip() for l in (text or '').split('\n') if l.strip()]
    for line in lines[:6]:
        name = _name_from_line(line)
        if name:
            return name
    return _name_from_email(extract_email(text or '')) or _name_from_filename(fallback_filename)


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
