from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages as flash_messages
from django.contrib.auth.models import Group
from django.utils import timezone
from datetime import timedelta
import secrets
from .models import Message, InviteCode

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

    chat_messages = Message.objects.order_by("-creation_date")[:50]

    return render(request, "core/chat.html", {"chat_messages": chat_messages})

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
