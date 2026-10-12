import pandas as pd
from .loaded_models import rf_model
from .feature_engineering import build_feature_row, features_for_model, FEATURE_ORDER
from .skill_fit import check_required_skills, combined_score
from ..models import JobPosting, MatchResult


def score_resume_against_job(resume, job):
    raw = build_feature_row(resume, job)
    features = features_for_model(raw)

    X = pd.DataFrame([features], columns=FEATURE_ORDER)
    if hasattr(rf_model, "feature_names_in_"):
        X = X[list(rf_model.feature_names_in_)]

    rf_prob = float(rf_model.predict_proba(X)[0][1])          # what the Random Forest says
    final = combined_score(rf_prob, check_required_skills(resume, job))   # model + required-skill check

    match, _ = MatchResult.objects.update_or_create(
        resume=resume,
        job=job,
        defaults={
            **features,
            "rf_prediction": rf_prob,
            "final_score": final,
        },
    )
    return match


def get_top_matches(resume, top_n=5):
    results = []
    for job in JobPosting.objects.all():
        results.append(score_resume_against_job(resume, job))
    results.sort(key=lambda m: (m.final_score or 0), reverse=True)
    return results[:top_n]