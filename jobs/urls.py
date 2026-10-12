from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_resume, name='upload_resume'),
    path('post-job/', views.post_job, name='post_job'),
    path('jobs/', views.job_list, name='job_list'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('candidates/ranking/', views.candidate_ranking, name='candidate_ranking'),
    path('candidates/', views.candidates, name='candidates'),
    path('result/<int:match_id>/', views.match_detail, name='match_detail'),
]