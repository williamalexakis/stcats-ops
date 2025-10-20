from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

User = get_user_model()

def home(request):
    return render(request, "core/home.html")

def healthcheck(request):
    return HttpResponse("OK", content_type="text/plain")

@login_required
def members(request):
    # Get all users and categorize them
    all_users = User.objects.all().select_related().prefetch_related('groups')
    
    admins = []
    teachers = []
    students = []
    
    for user in all_users:
        if user.is_superuser or user.groups.filter(name='admin').exists():
            admins.append(user)
        elif user.groups.filter(name='teacher').exists():
            teachers.append(user)
        else:
            students.append(user)
    
    context = {
        'admins': admins,
        'teachers': teachers,
        'students': students,
        'total_count': all_users.count(),
    }
    
    return render(request, "core/members.html", context)

# TODO: Unplaceholder this placeholder
def rooms(request):
    pass
