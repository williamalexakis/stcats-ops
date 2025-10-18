from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Announcement


@login_required
def announcement_list(request):
    announcements = Announcement.objects.order_by("-pinned", "-creation_date")[:50]

    return render(request, "core/announcements.html", {"announcements": announcements})
