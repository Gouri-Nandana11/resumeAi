from django.shortcuts import render, redirect, get_object_or_404
from .models import JobPosting, Resume, MatchResult
from .forms import JobPostingForm
from .resume_parser import extract_resume_info
from .ml.predict import score_resume_against_job, get_top_matches
from django.contrib import messages


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

        job = JobPosting.objects.get(id=job_id)

        for f in files:

            resume = Resume(
                resume_file=f,
                applied_job=job
            )

            resume.save()

            info = extract_resume_info(
                resume.resume_file.path,
                filename=f.name
            )

            resume.resume_text = info['resume_text']
            resume.candidate_name = info['candidate_name']
            resume.email = info['email']
            resume.experience_years = info['experience_years']
            resume.education_level = info.get('education_level', '')   # ← ADD THIS LINE



            resume.save()

            # Run ML matching
            match_result = score_resume_against_job(
                resume,
                job
            )

        return render(
            request,
            'jobs/matching_result.html',
            {
                'resume': resume,
                'job': job,
                'match': match_result
            }
        )

    return render(
        request,
        'jobs/upload_resume.html',
        {'jobs': jobs}
    )


def job_detail(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)
    resumes = job.resumes.all()
    return render(request, 'jobs/job_detail.html', {'job': job, 'resumes': resumes})

def dashboard(request):
    resume_count = Resume.objects.count()
    job_count = JobPosting.objects.count()
    match_count = MatchResult.objects.count()

    context = {
        'resume_count': resume_count,
        'job_count': job_count,
        'match_count': match_count,
    }

    return render(request, 'jobs/dashboard.html', context)