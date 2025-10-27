from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages as flash_messages
from django.contrib.auth.models import Group
from django.utils import timezone
from datetime import timedelta, date
import secrets
from .models import Message, InviteCode, Room, ScheduleEntry, Classroom, Subject, Course, AuditLog
from django.core.paginator import Paginator
from django.db.models import Sum

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

    # Get the room, or otherwise create a
    # default General room if none are available
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
            flash_messages.success(request, "Message sent.")

        else:

            flash_messages.error(request, "Message cannot be empty.")

        return redirect("chat")

    # Get messages from the room, sorted chronologically
    chat_messages = Message.objects.filter(room=room).select_related("author").order_by("-creation_date")[:100]
    chat_messages = list(reversed(chat_messages))
    context = {
        "chat_messages": chat_messages,
        "room": room
    }

    return render(request, "core/chat.html", context)

@login_required
def admin_dashboard(request):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to access this page.")

        return redirect("home")

    # Get statistics
    all_users = User.objects.all().select_related().prefetch_related("groups")
    total_users = all_users.count()
    admin_count = 0
    teacher_count = 0

    for user in all_users:

        if user.is_superuser or user.groups.filter(name="admin").exists():

            admin_count += 1

        elif user.groups.filter(name="teacher").exists():

            teacher_count += 1

    # Invite code stuff
    active_invites = InviteCode.objects.filter(remaining_uses__gt=0).count()
    total_invite_uses = InviteCode.objects.filter(remaining_uses__gt=0).aggregate(Sum('remaining_uses'))['remaining_uses__sum'] or 0

    # Schedule stuff
    total_schedule_entries = ScheduleEntry.objects.count()
    today = date.today()
    upcoming_entries = ScheduleEntry.objects.filter(date__gte=today).count()

    # Message stuff
    total_messages = Message.objects.count()
    announcement_count = Message.objects.filter(is_announcement=True).count()

    context = {
        "total_users": total_users,
        "admin_count": admin_count,
        "teacher_count": teacher_count,
        "active_invites": active_invites,
        "total_invite_uses": total_invite_uses,
        "total_schedule_entries": total_schedule_entries,
        "upcoming_entries": upcoming_entries,
        "total_messages": total_messages,
        "announcement_count": announcement_count
    }

    return render(request, "core/admin_dashboard.html", context)

@login_required
def admin_invites(request):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to access this page.")

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

        return redirect("admin_invites")

    # Get all invite codes
    invite_codes = InviteCode.objects.all().order_by("-creation_date")
    context = {"invite_codes" : invite_codes}

    return render(request, "core/admin_panel.html", context)


@login_required
def admin_audit_logs(request):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to access this page.")

        return redirect("home")

    # Get all audit logs
    logs_list = AuditLog.objects.all().select_related('actor')

    # Apply filters
    actor_filter = request.GET.get('actor')
    action_filter = request.GET.get('action')
    date_filter = request.GET.get('date')

    has_filters = any([actor_filter, action_filter, date_filter])

    if actor_filter:

        logs_list = logs_list.filter(actor_id=actor_filter)

    if action_filter:

        logs_list = logs_list.filter(action=action_filter)

    if date_filter:
        logs_list = logs_list.filter(creation_date__date=date_filter)

    # We let up to 10 logs per page
    paginator = Paginator(logs_list, 10)
    page_number = request.GET.get('page', 1)
    logs = paginator.get_page(page_number)

    # Get unique actors and actions for filters
    actors = User.objects.filter(auditlog__isnull=False).distinct().order_by('username')
    actions = AuditLog.objects.values_list('action', flat=True).distinct().order_by('action')
    context = {
        'logs': logs,
        'actors': actors,
        'actions': actions,
        'actor_filter': actor_filter,
        'action_filter': action_filter,
        'date_filter': date_filter,
        'has_filters': has_filters,
    }

    return render(request, "core/admin_audit_logs.html", context)

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

    return redirect("admin_invites")

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

        # Only allow editing your own messages
        if message.author != request.user:

            flash_messages.error(request, "You don't have permission to perform this action.")

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
                flash_messages.success(request, "Message updated.")

            else:

                flash_messages.error(request, "Message cannot be empty.")

            return redirect("chat")

        context = {
            "message" : message
        }

        return render(request, "core/edit_message.html", context)

    except Message.DoesNotExist:

        flash_messages.error(request, "Message not found.")

        return redirect("chat")

@login_required
def delete_message(request, message_id):
    try:

        message = Message.objects.get(id=message_id)
        can_delete = False

        # User can delete their own messages
        if message.author == request.user:

            can_delete = True

        # Admins can delete any message
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

            flash_messages.error(request, "You don't have permission to perform this action.")

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

@login_required
def scheduler(request):

    # Cleanup any expired entries
    ScheduleEntry.objects.cleanup_past_entries()

    # Get all the schedule entries
    entries_list = ScheduleEntry.objects.all().select_related('teacher', 'created_by', 'classroom', 'subject', 'course')

    # Apply filters
    teacher_filter = request.GET.get('teacher')
    classroom_filter = request.GET.get('classroom')
    subject_filter = request.GET.get('subject')
    course_filter = request.GET.get('course')
    date_filter = request.GET.get('date')
    has_filters = any([teacher_filter, classroom_filter, subject_filter, course_filter, date_filter])

    if teacher_filter:

        entries_list = entries_list.filter(teacher_id=teacher_filter)

    if classroom_filter:

        entries_list = entries_list.filter(classroom_id=classroom_filter)

    if subject_filter:

        entries_list = entries_list.filter(subject_id=subject_filter)

    if course_filter:

        entries_list = entries_list.filter(course_id=course_filter)

    if date_filter:

        entries_list = entries_list.filter(date=date_filter)

    # We allow up to 10 entries per page
    paginator = Paginator(entries_list, 10)
    page_number = request.GET.get('page', 1)
    entries = paginator.get_page(page_number)

    for entry in entries:

        entry.is_active = entry.is_active_now()

    # Get filter options
    teachers = User.objects.all().order_by('username')
    classrooms = Classroom.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    courses = Course.objects.all().order_by('name')

    context = {
        'entries': entries,
        'is_admin': request.user.is_superuser or request.user.groups.filter(name='admin').exists(),
        'teachers': teachers,
        'classrooms': classrooms,
        'subjects': subjects,
        'courses': courses,
        'teacher_filter': teacher_filter,
        'classroom_filter': classroom_filter,
        'subject_filter': subject_filter,
        'course_filter': course_filter,
        'date_filter': date_filter,
        'has_filters': has_filters,
    }

    return render(request, "core/scheduler.html", context)

@login_required
def create_schedule_entry(request):

    # Check if user is admin or superuser
    if not (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect('scheduler')

    if request.method == 'POST':

        teacher_id = request.POST.get('teacher')
        classroom_id = request.POST.get('classroom')
        subject_id = request.POST.get('subject')
        course_id = request.POST.get('course')
        date = request.POST.get('date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')

        try:

            teacher = User.objects.get(id=teacher_id)
            classroom = Classroom.objects.get(id=classroom_id)
            subject = Subject.objects.get(id=subject_id)
            course = Course.objects.get(id=course_id)

            ScheduleEntry.objects.create(
                teacher=teacher,
                classroom=classroom,
                subject=subject,
                course=course,
                date=date,
                start_time=start_time,
                end_time=end_time,
                created_by=request.user
            )
            flash_messages.success(request, "Schedule entry successfully created.")

            return redirect('scheduler')

        except User.DoesNotExist:

            flash_messages.error(request, "Selected teacher not found.")

        except (Classroom.DoesNotExist, Subject.DoesNotExist, Course.DoesNotExist):

            flash_messages.error(request, "Selected item not found.")

        except Exception as error:

            flash_messages.error(request, f"Error creating entry: {str(error)}")

    # Get all data for the form
    teachers = User.objects.all().order_by('username')
    classrooms = Classroom.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    courses = Course.objects.all().order_by('name')

    context = {
        'teachers': teachers,
        'classrooms': classrooms,
        'subjects': subjects,
        'courses': courses,
    }

    return render(request, "core/create_schedule_entry.html", context)

@login_required
def edit_schedule_entry(request, entry_id):

    # Check if user is admin or superuser
    if not (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect('scheduler')

    try:

        entry = ScheduleEntry.objects.get(id=entry_id)

        if request.method == 'POST':

            teacher_id = request.POST.get('teacher')
            classroom_id = request.POST.get('classroom')
            subject_id = request.POST.get('subject')
            course_id = request.POST.get('course')
            entry.date = request.POST.get('date')
            entry.start_time = request.POST.get('start_time')
            entry.end_time = request.POST.get('end_time')

            try:

                entry.teacher = User.objects.get(id=teacher_id)
                entry.classroom = Classroom.objects.get(id=classroom_id)
                entry.subject = Subject.objects.get(id=subject_id)
                entry.course = Course.objects.get(id=course_id)

                entry.save()
                flash_messages.success(request, "Schedule entry successfully updated.")

                return redirect('scheduler')

            except User.DoesNotExist:

                flash_messages.error(request, "Selected teacher not found.")

            except (Classroom.DoesNotExist, Subject.DoesNotExist, Course.DoesNotExist):

                flash_messages.error(request, "Selected item not found.")

        # Get all data for the form
        teachers = User.objects.all().order_by('username')
        classrooms = Classroom.objects.all().order_by('name')
        subjects = Subject.objects.all().order_by('name')
        courses = Course.objects.all().order_by('name')

        context = {
            'entry' : entry,
            'teachers' : teachers,
            'classrooms': classrooms,
            'subjects': subjects,
            'courses': courses,
        }

        return render(request, "core/edit_schedule_entry.html", context)

    except ScheduleEntry.DoesNotExist:

        flash_messages.error(request, "Schedule entry not found.")

        return redirect('scheduler')

@login_required
def delete_schedule_entry(request, entry_id):

    # Check if user is admin or superuser
    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("scheduler")

    try:

        entry = ScheduleEntry.objects.get(id=entry_id)

        entry.delete()
        flash_messages.success(request, "Schedule entry successfully deleted.")

    except ScheduleEntry.DoesNotExist:

        flash_messages.error(request, "Schedule entry not found.")

    return redirect('scheduler')
