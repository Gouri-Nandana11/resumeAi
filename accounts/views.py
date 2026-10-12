# accounts/views.py — fixed
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect



from django.shortcuts import redirect


def home(request):
    # Always show the login page when the root URL is opened
    return redirect('login')



@login_required(login_url='login')
def dashboard(request):
    return render(request, 'dashboard.html')