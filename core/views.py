from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from .models import Message

User = get_user_model()

def home(request):

    return render(request, "core/home.html")

def healthcheck():

    return HttpResponse("OK", content_type="text/plain")

@login_required
def members(request):

    all_users = User.objects.all().select_related().prefetch_related('groups')
    admins = []
    teachers = []

    for user in all_users:

        if user.is_superuser or user.groups.filter(name='admin').exists():

            admins.append(user)

        elif user.groups.filter(name='teacher').exists():

            teachers.append(user)

    context = {
        'admins': admins,
        'teachers': teachers,
        'total_count': all_users.count()
    }

    return render(request, "core/members.html", context)

@login_required
def chat(request):

    chat_messages = Message.objects.order_by("-creation_date")[:50]

    return render(request, "core/chat.html", {"chat_messages" : chat_messages})
