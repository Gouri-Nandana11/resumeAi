"""Plain-language explanation of a match: skills matched / related / missing, strengths and gaps."""

from .feature_engineering import extract_resume_skills, parse_required_skills, expand_job_skills
from .loaded_models import skill_domain_db

DISPLAY = {
    'sql': 'SQL', 'css': 'CSS', 'html': 'HTML', 'aws': 'AWS', 'api': 'API', 'php': 'PHP',
    'xml': 'XML', 'json': 'JSON', 'ui': 'UI', 'ux': 'UX', 'ai': 'AI', 'ml': 'ML', 'nlp': 'NLP',
    'oop': 'OOP', 'jwt': 'JWT', 'rest': 'REST', 'ios': 'iOS', 'ci/cd': 'CI/CD',
    'c#': 'C#', 'c++': 'C++', '.net': '.NET', 'asp.net': 'ASP.NET', 'node.js': 'Node.js',
    'nodejs': 'NodeJS', 'react.js': 'React.js', 'next.js': 'Next.js', 'vue.js': 'Vue.js',
    'javascript': 'JavaScript', 'typescript': 'TypeScript', 'mysql': 'MySQL',
    'postgresql': 'PostgreSQL', 'mongodb': 'MongoDB', 'github': 'GitHub',
}


def pretty_skill(skill):
    skill = str(skill).strip().lower()
    return ' '.join(DISPLAY.get(w, w.capitalize()) for w in skill.split(' ')) if skill not in DISPLAY else DISPLAY[skill]


# Job-level words that live in the skill database but are not skills ("fresher", "senior-level" ...)
LEVEL_WORDS = ('fresher', 'junior', 'senior', 'entry', 'experienced', 'intern', 'level', 'leadership')

# Two skills count as "related" when they appear under a similar set of job roles.
# This only affects what is displayed; the model's own features are untouched.
RELATED_THRESHOLD = 0.3


def _is_skill(name):
    return not any(w in name for w in LEVEL_WORDS)


def _roles(skill):
    return {str(r).lower() for r in skill_domain_db.get(skill, [])}


def _similarity(a, b):
    ra, rb = _roles(a), _roles(b)
    return len(ra & rb) / len(ra | rb) if ra and rb else 0.0


def explain_match(resume, job, match):
    resume_skills = {s for s in extract_resume_skills(resume.resume_text, getattr(resume, 'skills', '')) if _is_skill(s)}
    required = parse_required_skills(job.required_skills)
    job_skills = set(expand_job_skills(job.title, job.description, required))

    matched, related, missing = [], [], []
    for skill in required:
        if skill in resume_skills:
            matched.append(skill)
            continue
        best = max(sorted(resume_skills), key=lambda rs: _similarity(skill, rs), default=None)
        if best and _similarity(skill, best) >= RELATED_THRESHOLD:
            related.append((skill, best))
        else:
            missing.append(skill)

    extra = sorted((resume_skills & job_skills) - set(matched))[:12]

    # ---- strengths and gaps, in plain words ----
    strengths, gaps = [], []

    need, have = job.experience_required or 0, resume.experience_years or 0
    if need > 0:
        if have >= need:
            strengths.append(f"Meets the experience requirement ({have} yrs vs {need} needed)")
        elif have == 0:
            gaps.append(f"No years of experience found in the resume (job needs {need})")
        else:
            gaps.append(f"Below the experience requirement ({have} yrs vs {need} needed)")
    elif have > 0:
        strengths.append(f"{have} yrs of experience")

    if required:
        if len(matched) == len(required):
            strengths.append(f"Has all {len(required)} required skills")
        elif matched:
            strengths.append(f"Has {len(matched)} of {len(required)} required skills")
        else:
            gaps.append("None of the required skills were found in the resume")
        if missing:
            gaps.append("Missing skills: " + ", ".join(pretty_skill(s) for s in missing))
    elif extra:
        strengths.append(f"Resume mentions {len(extra)} skills relevant to this role")

    if resume.education_level:
        strengths.append(f"Education: {resume.education_level}")
    else:
        gaps.append("Education level not found in the resume")

    if (match.certification_present or 0) >= 0.5:
        strengths.append("Mentions a certification")
    else:
        gaps.append("No certifications mentioned")

    return {
        'has_required': bool(required),
        'required_total': len(required),
        'matched': [pretty_skill(s) for s in matched],
        'related': [(pretty_skill(a), pretty_skill(b)) for a, b in related],
        'missing': [pretty_skill(s) for s in missing],
        'extra': [pretty_skill(s) for s in extra],
        'strengths': strengths,
        'gaps': gaps,
    }