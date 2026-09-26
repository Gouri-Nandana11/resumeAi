# jobs/ml/feature_engineering.py
"""
Feature engineering aligned with training pipeline.
Features (exact order used by models):
1. semantic_skill_score
2. skill_coverage
3. tfidf_similarity
4. experience_match
5. education_encoded
6. certification_present
"""

import re
from sklearn.metrics.pairwise import cosine_similarity
from .loaded_models import tfidf_vectorizer, skill_domain_db

# Must match training
FEATURE_ORDER = [
    "semantic_skill_score",
    "skill_coverage",
    "tfidf_similarity",
    "experience_match",
    "education_encoded",
    "certification_present",
]

EDUCATION_RANK = {
    "": 0,
    "Diploma": 1,
    "Bachelors": 2,
    "Masters": 3,
    "PhD": 4,
}

FRONTEND_SKILLS = [
    "html", "css", "javascript", "typescript", "react", "angular", "vue",
    "next.js", "redux", "bootstrap", "tailwind",
]

BACKEND_SKILLS = [
    "python", "java", "node.js", "nodejs", "django", "flask", "spring",
    "express", "sql", "mysql", "postgresql", "mongodb", "api", "rest",
    "docker", "microservices", "c#", "asp.net",
]


def _clean_text(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\s\+\.#]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_resume_skills(resume_text, skills_field=""):
    """
    Extract skills using:
    1) optional comma-separated skills field
    2) word-boundary search against skill_domain_db keys
    """
    found = set()

    # from explicit skills field on Resume model
    if skills_field:
        for s in str(skills_field).split(","):
            s = s.strip().lower()
            if s:
                found.add(s)

    text = _clean_text(resume_text)
    for skill in skill_domain_db.keys():
        skill_l = str(skill).lower().strip()
        if not skill_l:
            continue
        if re.search(r"\b" + re.escape(skill_l) + r"\b", text):
            found.add(skill_l)

    # also catch common front/back skills not always in db
    for skill in FRONTEND_SKILLS + BACKEND_SKILLS:
        if re.search(r"\b" + re.escape(skill) + r"\b", text):
            found.add(skill)

    return list(found)


def parse_required_skills(required_skills_str):
    if not required_skills_str:
        return []
    return [s.strip().lower() for s in str(required_skills_str).split(",") if s.strip()]


def expand_job_skills(job_title, job_description, required_skills):
    """
    Expand job skills using:
    - required_skills field
    - skills mentioned in description
    - frontend/backend role keywords
    - skill_domain_db title links
    """
    expanded = set(required_skills or [])
    title = _clean_text(job_title)
    desc = _clean_text(job_description)
    combined = f"{title} {desc}"

    # skills mentioned in text
    for skill in list(skill_domain_db.keys()) + FRONTEND_SKILLS + BACKEND_SKILLS:
        skill_l = str(skill).lower().strip()
        if skill_l and re.search(r"\b" + re.escape(skill_l) + r"\b", combined):
            expanded.add(skill_l)

    # explicit role expansion
    if any(w in combined for w in ["backend", "back-end", "back end"]):
        expanded.update(BACKEND_SKILLS)
    if any(w in combined for w in ["frontend", "front-end", "front end"]):
        expanded.update(FRONTEND_SKILLS)

    # if title matches known roles in skill_domain_db values, add those skills
    for skill, roles in skill_domain_db.items():
        for role in roles:
            role_l = str(role).lower()
            if role_l in title or title in role_l:
                expanded.add(str(skill).lower())

    return list(expanded)


def compute_skill_coverage(resume_skills, job_skills):
    """Exact overlap: matched required skills / total required skills"""
    if not job_skills:
        return 0.0
    resume_set = set(s.lower() for s in resume_skills)
    required_set = set(s.lower() for s in job_skills)
    overlap = resume_set & required_set
    return round(len(overlap) / len(required_set), 4)


def compute_semantic_skill_score(resume_skills, job_skills):
    if not job_skills or not resume_skills:
        return 0.0

    resume_skills = [s.lower() for s in resume_skills]
    job_skills = [s.lower() for s in job_skills]
    matched = 0

    for js in job_skills:
        if js in resume_skills:
            matched += 1
            continue

        j_roles = set(str(r).lower() for r in skill_domain_db.get(js, []))
        if not j_roles:
            continue

        for rs in resume_skills:
            r_roles = set(str(r).lower() for r in skill_domain_db.get(rs, []))
            if j_roles & r_roles:
                matched += 1
                break

    return round(matched / len(job_skills), 4)


def compute_experience_match(resume_experience_years, job_experience_required):
    try:
        cand = float(resume_experience_years or 0)
        req = float(job_experience_required or 0)
    except (TypeError, ValueError):
        return 0.0

    # If job does not specify experience, give neutral score (not perfect)
    if req <= 0:
        return 0.5

    return round(min(cand / req, 1.0), 4)


def compute_education_encoded(education_level):
    return float(EDUCATION_RANK.get(education_level or "", 0))


def compute_certification_present(resume_text):
    text = _clean_text(resume_text)
    keywords = [
        "certified", "certification", "aws", "azure", "pmp", "scrum",
        "google cloud", "microsoft certified"
    ]
    return 1.0 if any(kw in text for kw in keywords) else 0.0


def compute_tfidf_similarity(resume_text, job_description):
    if not resume_text or not job_description:
        return 0.0
    resume_vec = tfidf_vectorizer.transform([_clean_text(resume_text)])
    job_vec = tfidf_vectorizer.transform([_clean_text(job_description)])
    return round(float(cosine_similarity(resume_vec, job_vec)[0][0]), 4)


def build_feature_row(resume, job):
    """
    Build feature dict for one Resume vs one JobPosting.
    Matches training feature names/order.
    """
    resume_text = resume.resume_text or ""
    job_title = job.title or ""
    job_description = job.description or ""

    resume_skills = extract_resume_skills(resume_text, getattr(resume, "skills", ""))
    required = parse_required_skills(job.required_skills)
    job_skills = expand_job_skills(job_title, job_description, required)

    features = {
        "semantic_skill_score": compute_semantic_skill_score(resume_skills, job_skills),
        "skill_coverage": compute_skill_coverage(resume_skills, job_skills),
        "tfidf_similarity": compute_tfidf_similarity(resume_text, job_description),
        "experience_match": compute_experience_match(
            resume.experience_years, job.experience_required
        ),
        "education_encoded": compute_education_encoded(resume.education_level),
        "certification_present": compute_certification_present(resume_text),
    }

    # helpful debug fields (not passed to model)
    features["_debug_resume_skills"] = resume_skills
    features["_debug_job_skills"] = job_skills
    return features


def features_for_model(features_dict):
    """Return clean dict with only model columns."""
    return {k: float(features_dict.get(k, 0.0)) for k in FEATURE_ORDER}