"""Rule-based check of the job's required skills against a resume.

The Random Forest cannot tell a Python developer from a Node.js developer on its own
(its skill features are close to 0.9 for almost any tech resume), so the required
skills are checked explicitly here and blended into the final score.
"""

import re

from .feature_engineering import _clean_text, extract_resume_skills, FRONTEND_SKILLS, BACKEND_SKILLS
from .loaded_models import skill_domain_db

RELATED_THRESHOLD = 0.3
RELATED_CREDIT = 0.25     # a related skill earns a quarter of a point, an exact match earns one
RF_WEIGHT = 0.6           # final score = 60% model probability + 40% required-skill fit
CORE_PENALTY = 0.6        # multiplier when none of the job's core skills is in the resume
LEVEL_WORDS = ('fresher', 'junior', 'senior', 'entry', 'experienced', 'intern', 'level', 'leadership')

# cleaned skill text  ->  original key in skill_domain_db (so role lookups still work)
_VOCAB = {}
for _k in list(skill_domain_db.keys()) + FRONTEND_SKILLS + BACKEND_SKILLS:
    _clean = _clean_text(_k)
    if _clean and _clean not in _VOCAB:
        _VOCAB[_clean] = str(_k).lower().strip()


_FILLER = {'development', 'programming', 'basics', 'fundamentals', 'framework', 'skills'}


def _core(skill):
    """'REST API Development' -> 'rest api', 'REST APIs' -> 'rest api', 'Python Programming' -> 'python'."""
    words = _clean_text(skill).split()
    while len(words) > 1 and words[-1] in _FILLER:
        words.pop()
    if words and len(words[-1]) > 3 and words[-1].endswith('s') and not words[-1].endswith('ss'):
        words[-1] = words[-1][:-1]
    return ' '.join(words)


def _roles(skill):
    return {str(r).lower() for r in skill_domain_db.get(skill, [])}


def _similarity(a, b):
    ra, rb = _roles(a), _roles(b)
    return len(ra & rb) / len(ra | rb) if ra and rb else 0.0


ROLE_WORDS = {'developer', 'engineer', 'analyst', 'programmer', 'designer', 'administrator',
              'architect', 'manager', 'tester', 'scientist', 'specialist', 'consultant'}
GENERIC_CORE = {'frontend', 'backend', 'front end', 'back end', 'full stack', 'fresher', 'junior',
                'senior', 'software', 'web', 'data', 'application', 'applications', 'mobile', 'cloud'}


def _skills_in(chunk):
    """Known skills inside a piece of text. Keeps the longest match ('rest api', not 'rest' + 'api')."""
    text = _clean_text(chunk)
    spans = []
    for clean, original in _VOCAB.items():
        for m in re.finditer(r'\b' + re.escape(clean) + r'\b', text):
            spans.append((m.start(), m.end(), original))
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept = []
    for s in spans:
        if not any(k[0] <= s[0] and s[1] <= k[1] for k in kept):
            kept.append(s)
    seen, result = set(), []
    for _, _, skill in kept:
        if skill not in seen:
            seen.add(skill)
            result.append(skill)
    return result


def required_skill_groups(required_text):
    """Turn whatever HR typed into a list of requirements; each requirement is a list of alternatives.

    "Python Programming, Django Or Flask"  ->  [['python'], ['django', 'flask']]
    """
    groups = []
    for chunk in re.split(r'[,;\n\u2022]+|\.\s+', str(required_text or '')):
        chunk = chunk.strip(' .')
        if not chunk:
            continue
        skills = _skills_in(chunk)
        if not skills:
            plain = _clean_text(chunk)
            if plain and len(plain.split()) <= 3:       # a skill that is not in the database
                groups.append([plain])
            continue
        if re.search(r'\bor\b', chunk, flags=re.I) and len(skills) > 1:
            groups.append(skills)                       # any one of them is enough
        else:
            groups.extend([s] for s in skills)
    unique, seen = [], set()
    for g in groups:
        key = tuple(g)
        if key not in seen:
            seen.add(key)
            unique.append(g)
    return unique


def check_required_skills(resume, job):
    required_text = job.required_skills
    # If HR left it blank, use title + description as the skill source
    if not str(required_text or "").strip():
        required_text = f"{job.title or ''}. {job.description or ''}"

    groups = required_skill_groups(required_text)
    resume_text = _clean_text(resume.resume_text)
    resume_skills = {
        s for s in extract_resume_skills(resume.resume_text, getattr(resume, "skills", ""))
        if not any(w in s for w in LEVEL_WORDS)
    }
    resume_cores = {_core(s) for s in resume_skills}

    def has(skill):
        core = _core(skill)
        return (
            skill in resume_skills
            or core in resume_cores
            or bool(re.search(r"\b" + re.escape(core) + r"s?\b", resume_text))
        )

    matched, related, missing = [], [], []
    for group in groups:
        hit = next((s for s in group if has(s)), None)
        if hit:
            matched.append(hit)
            continue
        best = max(
            ((s, rs, _similarity(s, rs)) for s in group for rs in sorted(resume_skills)),
            key=lambda t: t[2],
            default=None,
        )
        if best and best[2] >= RELATED_THRESHOLD:
            related.append((best[0], best[1]))
        else:
            missing.append(" / ".join(group))

    total = len(groups)
    fit = (len(matched) + RELATED_CREDIT * len(related)) / total if total else None

    core = core_skills(job.title)
    core_found = [c for c in core if has(c)]
    return {
        "total": total,
        "matched": matched,
        "related": related,
        "missing": missing,
        "fit": fit,
        "core": core,
        "core_missing": core if core and not core_found else [],
    }

def core_skills(job_title):
    """The skills a job is named after: 'Python Django Backend Developer' -> ['python', 'django']."""
    core = []
    for skill in _skills_in(job_title):
        words = skill.split()
        while words and words[-1] in ROLE_WORDS:
            words.pop()
        phrase = ' '.join(words)
        if (not phrase or phrase in GENERIC_CORE or any(w in phrase for w in LEVEL_WORDS)
                or phrase not in _VOCAB or phrase in core):
            continue
        core.append(phrase)
    return core


def combined_score(rf_probability, check):
    """Blend the model probability with the required-skill fit, then apply the core-skill rule."""
    if check['fit'] is None:
        score = rf_probability
    else:
        score = RF_WEIGHT * rf_probability + (1 - RF_WEIGHT) * check['fit']
    if check['core_missing']:
        score *= CORE_PENALTY
    return score