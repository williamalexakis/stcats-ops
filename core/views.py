from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages as flash_messages
from django.contrib.auth.models import Group
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta, date
from .models import InviteCode, ScheduleEntry, Classroom, Subject, Course, AuditLog
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Sum, Q
from typing import Optional
import secrets
import csv

User = get_user_model()

FLASH_LEVEL_MAP = {
    "success": flash_messages.success,
    "error": flash_messages.error,
    "warning": flash_messages.warning,
    "info": flash_messages.info,
}

def ajax_or_redirect(
    request: HttpRequest,
    success: bool,
    message: str,
    redirect_name: str,
    level: Optional[str] = None,
    status_code: Optional[int] = None,
) -> HttpResponse:

    """Return a JSON response for AJAX callers or redirect with flash messaging."""

    level = level or ("success" if success else "error")
    status_code = status_code or (200 if success else 400)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":

        return JsonResponse({
            "success": success,
            "message": message,
            "level": level,
        }, status=status_code)

    flash_handler = FLASH_LEVEL_MAP.get(level, flash_messages.info)
    flash_handler(request, message)

    return redirect(redirect_name)


@login_required
def code_editor(request: HttpRequest) -> HttpResponse:

    default_example = f"print(\"Hello, {request.user.get_username()}!\")\n"

    context = {
        "initial_code" : default_example
    }

    return render(request, "core/code_editor.html", context)

def home(request: HttpRequest) -> HttpResponse:

    upcoming_entries = []

    if request.user.is_authenticated:

        now = timezone.localtime()
        today = now.date()
        current_time = now.time()

        upcoming_entries = list(
            ScheduleEntry.objects.filter(
                teacher=request.user
            ).filter(
                Q(date__gt=today) | Q(date=today, end_time__gte=current_time)
            ).select_related("classroom", "subject", "course").order_by("date", "start_time")[:5]
        )

    if request.GET.get("partial") == "upcoming":

        return render(request, "core/partials/home_schedule.html", {
            "upcoming_entries": upcoming_entries
        })

    context = {
        "upcoming_entries": upcoming_entries
    }

    return render(request, "core/home.html", context)

def healthcheck(request: HttpRequest) -> HttpResponse:

    return HttpResponse("OK", content_type="text/plain")

@login_required
def members(request: HttpRequest) -> HttpResponse:

    """Group users by role for the members page."""

    all_users = list(User.objects.all().prefetch_related("groups"))
    admins = []
    teachers = []

    for user in all_users:

        group_names = {group.name for group in user.groups.all()}

        if user.is_superuser or "admin" in group_names:

            admins.append(user)

        elif "teacher" in group_names:

            teachers.append(user)

    admin_superusers = sorted((user for user in admins if user.is_superuser), key=lambda user: user.username.lower())
    admin_staff = sorted((user for user in admins if not user.is_superuser), key=lambda user: user.username.lower())
    admins = admin_superusers + admin_staff  # Keep superusers ahead of staff admins in rendering
    teachers = sorted(teachers, key=lambda user: user.username.lower())

    context = {
        "admins" : admins,
        "teachers" : teachers,
        "total_count" : len(all_users)
    }

    if request.GET.get("partial") == "1":

        return render(request, "core/partials/members_content.html", context)

    return render(request, "core/members.html", context)

@login_required
def admin_dashboard(request: HttpRequest) -> HttpResponse:

    """Gather high-level statistics for the administrative dashboard view."""

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You do not have permission to access this page.")

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

    context = {
        "total_users": total_users,
        "admin_count": admin_count,
        "teacher_count": teacher_count,
        "active_invites": active_invites,
        "total_invite_uses": total_invite_uses,
        "total_schedule_entries": total_schedule_entries,
        "upcoming_entries": upcoming_entries
    }

    return render(request, "core/admin_dashboard.html", context)

@login_required
def admin_invites(request: HttpRequest) -> HttpResponse:

    """Generate invite codes for admins and render the existing code list."""

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to access this page.", "home", status_code=403)

    if request.method == "POST":

        # Generate an invite code
        code = secrets.token_urlsafe(16)
        try:

            uses = int(request.POST.get("uses", 1))

        except (TypeError, ValueError):

            return ajax_or_redirect(request, False, "Number of uses must be a positive integer.", "admin_invites", status_code=400)

        if uses < 1:

            return ajax_or_redirect(request, False, "Number of uses must be at least 1.", "admin_invites", status_code=400)

        expiry_days = request.POST.get("expiry_days", "")
        expiration_date = None

        if expiry_days:

            try:

                days = int(expiry_days)

            except (TypeError, ValueError):

                return ajax_or_redirect(request, False, "Expiration days must be a positive integer.", "admin_invites", status_code=400)

            if days < 1:

                return ajax_or_redirect(request, False, "Expiration days must be at least 1.", "admin_invites", status_code=400)

            expiration_date = timezone.now() + timedelta(days=days)

        InviteCode.objects.create(
            code=code,
            creator=request.user,
            remaining_uses=uses,
            expiration_date=expiration_date
        )

        return ajax_or_redirect(request, True, f"Invite code created. Code: {code}", "admin_invites")

    # Get all invite codes
    invite_codes = InviteCode.objects.all().order_by("-creation_date")
    context = {"invite_codes" : invite_codes}

    if request.GET.get("partial") == "1":

        return render(request, "core/partials/admin_invites.html", context)

    return render(request, "core/admin_panel.html", context)


@login_required
def admin_audit_logs(request: HttpRequest) -> HttpResponse:

    """Render the audit log list with filtering and pagination for admins."""

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to access this page.", "home", status_code=403)

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

    if request.GET.get("partial") == "1":

        return render(request, "core/partials/admin_audit_logs.html", context)

    return render(request, "core/admin_audit_logs.html", context)

@login_required
@require_POST
def delete_invite_code(request: HttpRequest, code_id: int) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "home", status_code=403)

    try:

        invite_code = InviteCode.objects.get(id=code_id)

    except InviteCode.DoesNotExist:

        return ajax_or_redirect(request, False, "Invite code not found.", "admin_invites", status_code=404)

    invite_code.delete()

    return ajax_or_redirect(request, True, "Invite code successfully deleted.", "admin_invites")

@login_required
@require_POST
def promote_user(request: HttpRequest, user_id: int) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "members", status_code=403)

    try:

        user = User.objects.get(id=user_id)

    except User.DoesNotExist:

        return ajax_or_redirect(request, False, "User not found.", "members", status_code=404)

    if user.is_superuser:

        return ajax_or_redirect(request, False, "Cannot modify superuser accounts.", "members", status_code=400)

    try:

        admin_group = Group.objects.get(name="admin")

    except Group.DoesNotExist:

        return ajax_or_redirect(request, False, "Admin group not found.", "members", status_code=500)

    user.groups.clear()
    user.groups.add(admin_group)

    return ajax_or_redirect(request, True, f"User '{user.username}' has been promoted to admin.", "members")

@login_required
@require_POST
def demote_user(request: HttpRequest, user_id: int) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "members", status_code=403)

    try:

        user = User.objects.get(id=user_id)

    except User.DoesNotExist:

        return ajax_or_redirect(request, False, "User not found.", "members", status_code=404)

    if user.is_superuser:

        return ajax_or_redirect(request, False, "Cannot modify superuser accounts.", "members", status_code=400)

    if user == request.user:

        return ajax_or_redirect(request, False, "You cannot change your own administrative status.", "members", status_code=400)

    try:

        teacher_group = Group.objects.get(name="teacher")

    except Group.DoesNotExist:

        return ajax_or_redirect(request, False, "Teacher group not found.", "members", status_code=500)

    user.groups.clear()
    user.groups.add(teacher_group)

    return ajax_or_redirect(request, True, f"User '{user.username}' has been demoted to teacher.", "members")

@login_required
@require_POST
def remove_user(request: HttpRequest, user_id: int) -> HttpResponse:
    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "members", status_code=403)

    try:

        user = User.objects.get(id=user_id)

    except User.DoesNotExist:

        return ajax_or_redirect(request, False, "User not found.", "members", status_code=404)

    if user.is_superuser:

        return ajax_or_redirect(request, False, "Cannot remove superuser accounts.", "members", status_code=400)

    if user == request.user:

        return ajax_or_redirect(request, False, "Cannot remove your own account.", "members", status_code=400)

    username = user.username
    try:

        user.delete()

    except ProtectedError:

        return ajax_or_redirect(
            request,
            False,
            "Cannot remove this account because it is referenced by existing records.",
            "members",
            status_code=409
        )

    return ajax_or_redirect(request, True, f"User '{username}' has been removed.", "members")

@login_required
def scheduler(request: HttpRequest) -> HttpResponse:

    """List schedule entries with filtering, pagination, and active entry flags."""

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

        entry.is_active = entry.is_active_now()  # Flag active entries so templates can highlight them

    # Get filter options
    teachers = User.objects.all().order_by('username')
    classrooms = Classroom.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    courses = Course.objects.all().order_by('name')

    # Num of entries for the title badge thing
    entry_num = len(entries)

    context = {
        'entries' : entries,
        'entry_num' : entry_num,
        'is_admin' : request.user.is_superuser or request.user.groups.filter(name='admin').exists(),
        'teachers' : teachers,
        'classrooms' : classrooms,
        'subjects' : subjects,
        'courses' : courses,
        'teacher_filter' : teacher_filter,
        'classroom_filter' : classroom_filter,
        'subject_filter' : subject_filter,
        'course_filter' : course_filter,
        'date_filter' : date_filter,
        'has_filters' : has_filters,
    }

    if request.GET.get("partial") == "1":

        return render(request, "core/partials/scheduler_content.html", context)

    return render(request, "core/scheduler.html", context)

@login_required
def create_schedule_entry(request: HttpRequest) -> HttpResponse:

    """Create a schedule entry after validating admin permissions and selections."""

    # Check if user is admin or superuser
    if not (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):

        flash_messages.error(request, "You do not have permission to perform this action.")

        return redirect('scheduler')

    if request.method == 'POST':

        teacher_id = request.POST.get('teacher')
        classroom_id = request.POST.get('classroom')
        subject_id = request.POST.get('subject')
        course_id = request.POST.get('course')
        date_value = request.POST.get('date')
        start_time_value = request.POST.get('start_time')
        end_time_value = request.POST.get('end_time')

        errors = []

        if not all([teacher_id, classroom_id, subject_id, course_id, date_value, start_time_value, end_time_value]):

            errors.append("All fields are required.")

        try:

            entry_date = datetime.strptime(date_value, "%Y-%m-%d").date() if date_value else None

        except (TypeError, ValueError):

            entry_date = None
            errors.append("A valid date is required.")

        def parse_time(value: Optional[str]):

            try:

                return datetime.strptime(value, "%H:%M").time() if value else None

            except (TypeError, ValueError):

                return None

        start_time = parse_time(start_time_value)
        end_time = parse_time(end_time_value)

        if start_time is None:

            errors.append("A valid start time is required.")

        if end_time is None:

            errors.append("A valid end time is required.")

        if start_time and end_time and start_time >= end_time:

            errors.append("End time must be after the start time.")

        if errors:

            for message_text in errors:

                flash_messages.error(request, message_text)

            return redirect('scheduler')

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
                date=entry_date,
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
def edit_schedule_entry(request: HttpRequest, entry_id: int) -> HttpResponse:

    """Update a schedule entry after validating admin permissions and selections."""

    # Check if user is admin or superuser
    if not (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):

        flash_messages.error(request, "You do not have permission to perform this action.")

        return redirect('scheduler')

    try:

        entry = ScheduleEntry.objects.get(id=entry_id)

        if request.method == 'POST':

            teacher_id = request.POST.get('teacher')
            classroom_id = request.POST.get('classroom')
            subject_id = request.POST.get('subject')
            course_id = request.POST.get('course')
            date_value = request.POST.get('date')
            start_time_value = request.POST.get('start_time')
            end_time_value = request.POST.get('end_time')

            errors = []

            try:

                entry_date = datetime.strptime(date_value, "%Y-%m-%d").date() if date_value else None

            except (TypeError, ValueError):

                entry_date = None
                errors.append("A valid date is required.")

            def parse_time(value: Optional[str]):

                try:

                    return datetime.strptime(value, "%H:%M").time() if value else None

                except (TypeError, ValueError):

                    return None

            start_time = parse_time(start_time_value)
            end_time = parse_time(end_time_value)

            if not all([teacher_id, classroom_id, subject_id, course_id, date_value, start_time_value, end_time_value]):

                errors.append("All fields are required.")

            if start_time is None:

                errors.append("A valid start time is required.")

            if end_time is None:

                errors.append("A valid end time is required.")

            if start_time and end_time and start_time >= end_time:

                errors.append("End time must be after the start time.")

            if errors:

                for message_text in errors:

                    flash_messages.error(request, message_text)

                return redirect('scheduler')

            try:

                entry.teacher = User.objects.get(id=teacher_id)
                entry.classroom = Classroom.objects.get(id=classroom_id)
                entry.subject = Subject.objects.get(id=subject_id)
                entry.course = Course.objects.get(id=course_id)
                entry.date = entry_date
                entry.start_time = start_time
                entry.end_time = end_time

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
@require_POST
def delete_schedule_entry(request: HttpRequest, entry_id: int) -> HttpResponse:

    # Check if user is admin or superuser
    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "scheduler", status_code=403)

    try:

        entry = ScheduleEntry.objects.get(id=entry_id)

    except ScheduleEntry.DoesNotExist:

        return ajax_or_redirect(request, False, "Schedule entry not found.", "scheduler", status_code=404)

    entry.delete()

    return ajax_or_redirect(request, True, "Schedule entry successfully deleted.", "scheduler")

@login_required
def export_schedule_csv(request: HttpRequest) -> HttpResponse:

    """Export the filtered schedule entries as a CSV attachment."""

    def valid(val: Optional[str]) -> bool:

        return val and val != "None"

    teacher_filter = request.GET.get('teacher')
    classroom_filter = request.GET.get('classroom')
    subject_filter = request.GET.get('subject')
    course_filter = request.GET.get('course')
    date_filter = request.GET.get('date')
    qs = ScheduleEntry.objects.all().select_related(
        'teacher', 'classroom', 'subject', 'course'
    )

    if valid(teacher_filter):

        qs = qs.filter(teacher_id=teacher_filter)

    if valid(classroom_filter):

        qs = qs.filter(classroom_id=classroom_filter)

    if valid(subject_filter):

        qs = qs.filter(subject_id=subject_filter)

    if valid(course_filter):

        qs = qs.filter(course_id=course_filter)

    if valid(date_filter):

        qs = qs.filter(date=date_filter)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename=\"schedule.csv\"'

    writer = csv.writer(response)
    writer.writerow(["Date", "Start Time", "End Time", "Teacher", "Classroom", "Subject", "Course"])

    for e in qs:

        writer.writerow([
            e.date.strftime("%Y-%m-%d"),
            e.start_time.strftime("%H:%M"),
            e.end_time.strftime("%H:%M"),
            e.teacher.username,
            getattr(e.classroom, "display_name", getattr(e.classroom, "name", "")),
            getattr(e.subject, "display_name", getattr(e.subject, "name", "")),
            getattr(e.course, "display_name", getattr(e.course, "name", "")),
        ])

    return response
