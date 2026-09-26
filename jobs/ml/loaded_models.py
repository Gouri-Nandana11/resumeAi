import joblib
from pathlib import Path
from django.conf import settings

ML_DIR = Path(settings.BASE_DIR) / 'ml_artifacts'

rf_model = joblib.load(ML_DIR / 'rf_model.pkl')
xgb_model = joblib.load(ML_DIR / 'xgb_model.pkl')
tfidf_vectorizer = joblib.load(ML_DIR / 'tfidf_vectorizer.pkl')
skill_domain_db = joblib.load(ML_DIR / 'skill_domain.pkl')