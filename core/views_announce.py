from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Message

@login_required
def announcement_list(request):
    # Get all messages marked as announcements
    # Order by pinned status first, then by creation date (newest first)
    announcements = Message.objects.filter(
        is_announcement=True
    ).select_related('author', 'room').order_by('-is_pinned', '-creation_date')[:50]

    return render(request, "core/announcements.html", {"announcements": announcements})