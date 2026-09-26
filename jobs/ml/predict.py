import pandas as pd
from .loaded_models import rf_model, xgb_model
from .feature_engineering import build_feature_row, features_for_model, FEATURE_ORDER
from ..models import JobPosting, MatchResult


def score_resume_against_job(resume, job):
    raw = build_feature_row(resume, job)
    features = features_for_model(raw)
    # print("RESUME SKILLS:", raw.get("_debug_resume_skills"))
    # print("JOB SKILLS:", raw.get("_debug_job_skills"))
    # print("FEATURES:", features)
    # # ============================

    X = pd.DataFrame([features], columns=FEATURE_ORDER)

    if hasattr(xgb_model, "feature_names_in_"):
        X = X[list(xgb_model.feature_names_in_)]

    rf_prob = float(rf_model.predict_proba(X)[0][1])
    xgb_prob = float(xgb_model.predict_proba(X)[0][1])
    final_score = (rf_prob + xgb_prob) / 2

    match, _ = MatchResult.objects.update_or_create(
        resume=resume,
        job=job,
        defaults={
            **features,
            "rf_prediction": rf_prob,
            "xgb_prediction": xgb_prob,
            "final_score": final_score,
        },
    )
    return match


def get_top_matches(resume, top_n=5):
    """Rank all jobs for one resume by final_score."""
    results = []
    for job in JobPosting.objects.all():
        match = score_resume_against_job(resume, job)
        results.append(match)
    results.sort(key=lambda m: (m.final_score or 0), reverse=True)
    return results[:top_n]