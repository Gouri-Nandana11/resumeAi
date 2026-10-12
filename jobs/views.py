from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from .models import JobPosting, Resume, MatchResult
from .forms import JobPostingForm
from .resume_parser import extract_resume_info
from .ml.predict import score_resume_against_job
from .ml.explain import explain_match
from django.db.models import Q


def post_job(request):
    if request.method == 'POST':
        form = JobPostingForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            if request.user.is_authenticated:
                job.posted_by = request.user
            job.save()
            return redirect('job_list')
    else:
        form = JobPostingForm()
    return render(request, 'jobs/post_job.html', {'form': form})


def job_list(request):
    jobs = JobPosting.objects.order_by('-created_at')
    return render(request, 'jobs/job_list.html', {'jobs': jobs})


def upload_resume(request):
    jobs = JobPosting.objects.all()

    if request.method == 'POST':
        job_id = request.POST.get('job_id')
        files = request.FILES.getlist('resumes')

        if not job_id:
            messages.error(request, 'Please select a job.')
            return redirect('upload_resume')
        if not files:
            messages.error(request, 'Please choose at least one resume file.')
            return redirect('upload_resume')

        job = get_object_or_404(JobPosting, id=job_id)
        matches = []

        for f in files:
            resume = Resume(resume_file=f, applied_job=job)
            resume.save()

            info = extract_resume_info(resume.resume_file.path, filename=f.name)
            resume.resume_text = info['resume_text']
            resume.candidate_name = info['candidate_name']
            resume.email = info['email']
            resume.experience_years = info['experience_years']
            resume.education_level = info.get('education_level', '')
            resume.save()

            matches.append(score_resume_against_job(resume, job))

        # one resume -> its result page; several -> the ranked list
        if len(matches) == 1:
            return redirect('match_detail', match_id=matches[0].id)

        messages.success(request, f'{len(matches)} resumes analysed for {job.title}.')
        return redirect(f"{reverse('candidate_ranking')}?job_id={job.id}")

    return render(request, 'jobs/upload_resume.html', {
        'jobs': jobs,
        'preselected_job_id': request.GET.get('job_id', ''),
    })
def _factor_rows(match):
    pct = lambda value: round((value or 0) * 100)
    return [
        {'label': 'Skill relevance', 'percent': pct(match.semantic_skill_score),
         'hint': "How closely the candidate's skills belong to the same field as the job (related skills count)"},
        {'label': 'Keyword coverage', 'percent': pct(match.skill_coverage),
         'hint': 'Share of the skills linked to this role (from its title and description) found in the resume'},
        {'label': 'Text similarity', 'percent': pct(match.tfidf_similarity),
         'hint': 'How much the resume wording overlaps with the job description'},
        {'label': 'Experience', 'percent': pct(match.experience_match),
         'hint': 'Candidate years compared with the years the job requires'},
    ]


def match_detail(request, match_id):
    match = get_object_or_404(MatchResult.objects.select_related('resume', 'job'), id=match_id)
    same_job = MatchResult.objects.filter(job=match.job)
    rank = same_job.filter(final_score__gt=match.final_score or 0).count() + 1
    return render(request, 'jobs/match_detail.html', {
        'match': match,
        'resume': match.resume,
        'job': match.job,
        'rank': rank,
        'total': same_job.count(),
        'factors': _factor_rows(match),
        'explain': explain_match(match.resume, match.job, match),
    })


def candidate_ranking(request):
    jobs = JobPosting.objects.order_by('title')
    job_id = request.GET.get('job_id', '')
    selected_job = None
    ranked_matches = []
    suitable_count = 0

    if job_id.isdigit():
        selected_job = get_object_or_404(JobPosting, id=int(job_id))
        ranked_matches = list(
            MatchResult.objects.filter(job=selected_job)
            .select_related('resume')
            .order_by('-final_score')
        )
        suitable_count = sum(1 for m in ranked_matches if m.is_suitable)

    return render(request, 'jobs/candidate_ranking.html', {
        'jobs': jobs,
        'selected_job': selected_job,
        'ranked_matches': ranked_matches,
        'suitable_count': suitable_count,
    })


def job_detail(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)
    resumes = job.resumes.all()
    return render(request, 'jobs/job_detail.html', {'job': job, 'resumes': resumes})


def dashboard(request):
    context = {
        'resume_count': Resume.objects.count(),
        'job_count': JobPosting.objects.count(),
        'match_count': MatchResult.objects.count(),
    }
    return render(request, 'jobs/dashboard.html', context)
def candidates(request):
    jobs = JobPosting.objects.order_by('title')
    q = request.GET.get('q', '').strip()
    job_id = request.GET.get('job_id', '')

    matches = MatchResult.objects.select_related('resume', 'job').order_by('-resume__uploaded_at')
    if job_id.isdigit():
        matches = matches.filter(job_id=int(job_id))
    if q:
        matches = matches.filter(
            Q(resume__candidate_name__icontains=q) | Q(resume__email__icontains=q)
        )

    return render(request, 'jobs/candidates.html', {
        'matches': matches,
        'jobs': jobs,
        'q': q,
        'selected_job_id': job_id,
    })