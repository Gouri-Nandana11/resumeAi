from django.db import models
from django.contrib.auth.models import User


class JobPosting(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    required_skills = models.TextField(
        blank=True,
        help_text="Comma-separated skills, e.g. Python, Django, SQL (optional)"
    )
    experience_required = models.PositiveIntegerField(help_text="Years of experience required")
    posted_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Resume(models.Model):
    EDUCATION_CHOICES = [
        ('Bachelors', 'Bachelors'),
        ('Masters', 'Masters'),
        ('PhD', 'PhD'),
        ('Diploma', 'Diploma'),
    ]

    candidate_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    resume_file = models.FileField(upload_to='resumes/')
    resume_text = models.TextField(blank=True, help_text="Auto-extracted text from resume_file")
    skills = models.TextField(blank=True, help_text="Comma-separated skills (optional)")
    experience_years = models.PositiveIntegerField(default=0)
    education_level = models.CharField(max_length=20, choices=EDUCATION_CHOICES, blank=True)
    applied_job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='resumes')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.candidate_name or 'Unnamed'} - {self.applied_job.title}"


class MatchResult(models.Model):
    """Features and Random Forest prediction for one resume against one job."""

    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name='match_results')
    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='match_results')

    semantic_skill_score = models.FloatField(default=0.0)
    skill_coverage = models.FloatField(default=0.0)
    tfidf_similarity = models.FloatField(default=0.0)
    experience_match = models.FloatField(default=0.0)
    education_encoded = models.FloatField(default=0.0)
    certification_present = models.FloatField(default=0.0)

    rf_prediction = models.FloatField(null=True, blank=True)
    final_score = models.FloatField(null=True, blank=True, help_text="Ranking key (same as rf_prediction)")

    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('resume', 'job')
        ordering = ['-final_score']

    @property
    def score_percent(self):
        return round((self.final_score or 0) * 100, 1)

    @property
    def is_suitable(self):
        return (self.final_score or 0) >= 0.5

    def __str__(self):
        return f"{self.resume.candidate_name or 'Unnamed'} vs {self.job.title}: {self.score_percent}%"