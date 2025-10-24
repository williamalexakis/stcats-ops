from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages as flash_messages
from django.contrib.auth.models import Group
from django.utils import timezone
from datetime import timedelta
import secrets
from .models import Message, InviteCode, Room

User = get_user_model()

def home(request):

    return render(request, "core/home.html")

def healthcheck(request):

    return HttpResponse("OK", content_type="text/plain")

@login_required
def members(request):

    all_users = User.objects.all().select_related().prefetch_related("groups")
    admins = []
    teachers = []

    for user in all_users:

        if user.is_superuser or user.groups.filter(name="admin").exists():

            admins.append(user)

        elif user.groups.filter(name="teacher").exists():

            teachers.append(user)

    context = {
        "admins" : admins,
        "teachers" : teachers,
        "total_count" : all_users.count()
    }

    return render(request, "core/members.html", context)

@login_required
def chat(request):
    # Get or create the default "General" room
    room, created = Room.objects.get_or_create(
        name="General",
        defaults={
            "creator": request.user,
            "is_private": False
        }
    )
    
    # Handle message posting
    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        is_announcement = request.POST.get("is_announcement") == "on"
        is_pinned = request.POST.get("is_pinned") == "on" if is_announcement else False
        
        if body:
            Message.objects.create(
                room=room,
                author=request.user,
                body=body,
                is_announcement=is_announcement,
                is_pinned=is_pinned
            )
            flash_messages.success(request, "Message sent!")
        else:
            flash_messages.error(request, "Message cannot be empty.")
        
        return redirect("chat")
    
    # Get messages from the room (newest first)
    chat_messages = Message.objects.filter(room=room).select_related("author").order_by("-creation_date")[:100]
    
    # Reverse to show oldest first in display
    chat_messages = list(reversed(chat_messages))
    
    context = {
        "chat_messages": chat_messages,
        "room": room
    }
    
    return render(request, "core/chat.html", context)

@login_required
def admin_panel(request):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to access the admin panel.")

        return redirect("home")

    if request.method == "POST":

        # Generate an invite code
        code = secrets.token_urlsafe(16)
        uses = int(request.POST.get("uses", 1))
        expiry_days = request.POST.get("expiry_days", "")
        expiration_date = None

        if expiry_days:

            expiration_date = timezone.now() + timedelta(days=int(expiry_days))

        InviteCode.objects.create(
            code=code,
            creator=request.user,
            remaining_uses=uses,
            expiration_date=expiration_date
        )

        flash_messages.success(request, f"Invite code created: {code}")

        return redirect("admin_panel")

    # Get all invite codes
    invite_codes = InviteCode.objects.all().order_by("-creation_date")
    context = {"invite_codes" : invite_codes}

    return render(request, "core/admin_panel.html", context)

@login_required
def delete_invite_code(request, code_id):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("home")

    try:

        invite_code = InviteCode.objects.get(id=code_id)

        invite_code.delete()
        flash_messages.success(request, "Invite code successfully deleted.")

    except InviteCode.DoesNotExist:

        flash_messages.error(request, "Invite code not found.")

    return redirect("admin_panel")


@login_required
def promote_user(request, user_id):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("members")

    try:

        user = User.objects.get(id=user_id)

        if user.is_superuser:

            flash_messages.error(request, "Cannot modify superuser accounts.")

            return redirect("members")

        admin_group = Group.objects.get(name="admin")

        user.groups.clear()
        user.groups.add(admin_group)
        flash_messages.success(request, f"User '{user.username}' has been promoted to admin.")

    except User.DoesNotExist:

        flash_messages.error(request, "User not found.")

    except Group.DoesNotExist:

        flash_messages.error(request, "Admin group not found.")

    return redirect('members')


@login_required
def edit_message(request, message_id):
    try:
        message = Message.objects.get(id=message_id)
        
        # Only allow editing own messages
        if message.author != request.user:
            flash_messages.error(request, "You can only edit your own messages.")
            return redirect('chat')
        
        if request.method == 'POST':
            body = request.POST.get('body', '').strip()
            is_announcement = request.POST.get('is_announcement') == 'on'
            is_pinned = request.POST.get('is_pinned') == 'on' if is_announcement else False
            
            if body:
                message.body = body
                message.is_announcement = is_announcement
                message.is_pinned = is_pinned
                message.edit_date = timezone.now()
                message.save()
                flash_messages.success(request, "Message updated!")
            else:
                flash_messages.error(request, "Message cannot be empty.")
            
            return redirect('chat')
        
        context = {
            'message': message
        }
        return render(request, "core/edit_message.html", context)
        
    except Message.DoesNotExist:
        flash_messages.error(request, "Message not found.")
        return redirect('chat')


@login_required
def delete_message(request, message_id):
    try:
        message = Message.objects.get(id=message_id)
        
        # Check permissions
        can_delete = False
        
        # User can delete their own messages
        if message.author == request.user:
            can_delete = True
        # Admins can delete any message except superuser messages
        elif (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):
            if not message.author.is_superuser:
                can_delete = True
            else:
                flash_messages.error(request, "Cannot delete superuser messages.")
                return redirect('chat')
        
        if can_delete:
            message.delete()
            flash_messages.success(request, "Message deleted.")
        else:
            flash_messages.error(request, "You don't have permission to delete this message.")
            
    except Message.DoesNotExist:
        flash_messages.error(request, "Message not found.")
    
    return redirect('chat')


@login_required
def demote_user(request, user_id):

    if not (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("members")

    try:

        user = User.objects.get(id=user_id)

        if user.is_superuser:

            flash_messages.error(request, "Cannot modify superuser accounts.")
            return redirect("members")

        teacher_group = Group.objects.get(name="teacher")

        user.groups.clear()
        user.groups.add(teacher_group)
        flash_messages.success(request, f"User '{user.username}' has been demoted to teacher.")

    except User.DoesNotExist:

        flash_messages.error(request, "User not found.")

    except Group.DoesNotExist:

        flash_messages.error(request, "Teacher group not found.")

    return redirect("members")

@login_required
def remove_user(request, user_id):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("members")

    try:

        user = User.objects.get(id=user_id)

        if user.is_superuser:

            flash_messages.error(request, "Cannot remove superuser accounts.")

            return redirect("members")

        if user == request.user:

            flash_messages.error(request, "Cannot remove your own account.")

            return redirect("members")

        username = user.username

        user.delete()
        flash_messages.success(request, f"User '{username}' has been removed.")

    except User.DoesNotExist:

        flash_messages.error(request, "User not found.")

    return redirect("members")
