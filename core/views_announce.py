from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Announcement

@login_required
def announcement_list(request):

    # Get all the announcements and filter
    # by date created or pin status
    announcements = Announcement.objects.order_by("-pinned", "-creation_date")[:50]

    return render(request, "core/announcements.html", {"announcements": announcements})
