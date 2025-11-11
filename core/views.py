# Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file.

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages as flash_messages
from django.contrib.auth.models import Group
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.template.loader import render_to_string
from datetime import datetime, timedelta, date
from uuid import uuid4, UUID
from collections import defaultdict
from urllib.parse import urlencode
from django.urls import reverse
import calendar
import hashlib
from .models import InviteCode, ScheduleEntry, Classroom, Subject, Course, ClassGroup, AuditLog
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Sum, Q, Count
from django.db import transaction
from typing import Optional, Dict
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
            ).select_related("classroom", "subject", "course", "group").order_by("date", "start_time")[:5]
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
def _build_scheduler_context(request: HttpRequest) -> dict:

    """Prepare scheduler context data shared between HTML and JSON responses."""

    # Get all the schedule entries
    entries_list = ScheduleEntry.objects.all().select_related('teacher', 'created_by', 'classroom', 'subject', 'course', 'group')

    # Apply filters
    teacher_filter = request.GET.get('teacher')
    classroom_filter = request.GET.get('classroom')
    subject_filter = request.GET.get('subject')
    course_filter = request.GET.get('course')
    group_filter = request.GET.get('group')
    date_filter = request.GET.get('date')
    status_filter = request.GET.get('status')

    valid_status_codes = {code for code, _ in ScheduleEntry.STATUS_CHOICES}
    if status_filter not in valid_status_codes:

        status_filter = None

    has_filters = any([
        teacher_filter,
        classroom_filter,
        subject_filter,
        course_filter,
        group_filter,
        date_filter,
        status_filter
    ])

    if teacher_filter:

        entries_list = entries_list.filter(teacher_id=teacher_filter)

    if classroom_filter:

        entries_list = entries_list.filter(classroom_id=classroom_filter)

    if subject_filter:

        entries_list = entries_list.filter(subject_id=subject_filter)

    if course_filter:

        entries_list = entries_list.filter(course_id=course_filter)

    if group_filter:

        entries_list = entries_list.filter(group_id=group_filter)

    if date_filter:

        entries_list = entries_list.filter(date=date_filter)

    now = timezone.localtime()
    today = now.date()
    current_time = now.time()

    if status_filter == ScheduleEntry.STATUS_ACTIVE:

        entries_list = entries_list.filter(
            date=today,
            start_time__lte=current_time,
            end_time__gte=current_time
        )

    elif status_filter == ScheduleEntry.STATUS_UPCOMING:

        entries_list = entries_list.filter(
            Q(date__gt=today) |
            Q(date=today, start_time__gt=current_time)
        )

    elif status_filter == ScheduleEntry.STATUS_FINISHED:

        entries_list = entries_list.filter(
            Q(date__lt=today) |
            Q(date=today, end_time__lt=current_time)
        )

    entries_list = entries_list.order_by('date', 'start_time', 'id')
    total_entries = entries_list.count()

    fallback_date = today

    if date_filter:

        try:

            fallback_date = datetime.strptime(date_filter, "%Y-%m-%d").date()

        except (TypeError, ValueError):

            fallback_date = today

    show_weekends = request.GET.get('weekends', '0') == '1'

    # Resolve the requested calendar month
    month_param = request.GET.get('month')
    year_param = request.GET.get('year')

    try:

        month_value = int(month_param) if month_param else fallback_date.month
        year_value = int(year_param) if year_param else fallback_date.year

        if month_value < 1 or month_value > 12:

            raise ValueError("Month out of range.")

    except (TypeError, ValueError):

        month_value = fallback_date.month
        year_value = fallback_date.year

    current_month_start = date(year_value, month_value, 1)

    _, month_days = calendar.monthrange(year_value, month_value)
    current_month_end = current_month_start + timedelta(days=month_days - 1)

    # Align calendar to start on Monday and end on Sunday
    calendar_start = current_month_start - timedelta(days=current_month_start.weekday())
    calendar_end = current_month_end + timedelta(days=(6 - current_month_end.weekday()))

    # Fetch entries required for the rendered window
    month_entries_qs = entries_list.filter(date__gte=calendar_start, date__lte=calendar_end)
    month_entries = list(month_entries_qs)

    recurrence_groups = {
        entry.recurrence_group
        for entry in month_entries
        if entry.recurrence_group
    }

    recurrence_counts: Dict[Optional[UUID], int] = {}

    if recurrence_groups:

        for row in ScheduleEntry.objects.filter(recurrence_group__in=recurrence_groups).values("recurrence_group").annotate(total=Count("id")):

            recurrence_counts[row["recurrence_group"]] = row["total"]

    entries_by_date: Dict[date, list[ScheduleEntry]] = defaultdict(list)

    status_label_map = dict(ScheduleEntry.STATUS_CHOICES)

    for entry in month_entries:

        status_code = entry.get_status(reference_date=today, reference_time=current_time)
        entry.status_code = status_code
        entry.status_label = status_label_map.get(status_code, status_code.title())
        entry.is_active = (status_code == ScheduleEntry.STATUS_ACTIVE)
        entry.is_owned_by_user = (entry.teacher_id == request.user.id)
        entry.subject_display = getattr(entry.subject, "display_name", None) or entry.subject.name
        entry.course_display = getattr(entry.course, "display_name", None) or entry.course.name
        entry.classroom_display = getattr(entry.classroom, "display_name", None) or entry.classroom.name
        entry.group_display = getattr(entry.group, "display_name", None) if entry.group else ""

        entry.recurrence_series_size = recurrence_counts.get(entry.recurrence_group, 1)
        entry.has_recurrence_peers = entry.recurrence_group is not None and entry.recurrence_series_size > 1
        entry.recurrence_label = ""
        if entry.recurrence_group and entry.recurrence_series_size and entry.recurrence_index:

            entry.recurrence_label = f"Series {entry.recurrence_index} of {entry.recurrence_series_size}"

        entries_by_date[entry.date].append(entry)

    # Pre-compute monthly counts for navigation badges
    monthly_counts: Dict[tuple[int, int], int] = defaultdict(int)

    for year_part, month_part in entries_list.values_list("date__year", "date__month"):

        monthly_counts[(year_part, month_part)] += 1

    def get_month_offset(year: int, month: int, offset: int) -> tuple[int, int]:

        total_months = (year * 12 + (month - 1)) + offset
        target_year = total_months // 12
        target_month = (total_months % 12) + 1

        return target_year, target_month

    prev_year, prev_month = get_month_offset(year_value, month_value, -1)
    next_year, next_month = get_month_offset(year_value, month_value, 1)

    nearby_months = []

    for offset in range(-2, 3):

        badge_year, badge_month = get_month_offset(year_value, month_value, offset)
        badge_key = (badge_year, badge_month)
        badge_count = monthly_counts.get(badge_key, 0)

        nearby_months.append({
            "label": date(badge_year, badge_month, 1).strftime("%b %Y"),
            "month": badge_month,
            "year": badge_year,
            "count": badge_count,
            "has_entries": badge_count > 0,
            "is_current": offset == 0,
            "is_current_month": (badge_year == today.year and badge_month == today.month),
            "offset": offset,
        })

    day_names = []

    for weekday in range(0, 7):

        is_weekend = weekday >= 5

        if not show_weekends and is_weekend:

            continue

        day_names.append({
            "label": calendar.day_abbr[weekday],
            "full": calendar.day_name[weekday],
            "is_weekend": is_weekend,
        })

    calendar_weeks = []
    pointer = calendar_start

    while pointer <= calendar_end:

        week_days = []

        for day_index in range(7):

            current_date = pointer + timedelta(days=day_index)
            day_entries = entries_by_date.get(current_date, [])

            is_weekend = current_date.weekday() >= 5
            is_hidden = (not show_weekends and is_weekend)

            week_days.append({
                "date": current_date,
                "is_current_month": current_date.month == month_value,
                "is_today": current_date == today,
                "entries": day_entries,
                "is_weekend": is_weekend,
                "is_hidden": is_hidden,
            })

        calendar_weeks.append({
            "week_number": pointer.isocalendar()[1],
            "days": week_days,
        })

        pointer += timedelta(days=7)

    visible_entry_count = sum(
        len(day["entries"])
        for week in calendar_weeks
        for day in week["days"]
        if day["is_current_month"]
    )

    state_basis = [
        ":".join([
            str(entry.id),
            entry.date.isoformat(),
            entry.start_time.isoformat(),
            entry.end_time.isoformat(),
            str(entry.teacher_id),
            entry.teacher.username,
            str(entry.classroom_id),
            entry.classroom.name,
            str(entry.subject_id),
            entry.subject.display_name,
            str(entry.course_id),
            entry.course.display_name,
            str(entry.group_id or ""),
            entry.group.display_name if entry.group else "",
            str(int(entry.is_active)),
            str(entry.recurrence_series_size),
            str(entry.recurrence_index),
            entry.status_code,
        ])
        for entry in month_entries
    ]
    calendar_state_token = hashlib.sha256("|".join(state_basis).encode("utf-8")).hexdigest() if state_basis else "0"

    base_query_params = {
        "teacher": teacher_filter,
        "classroom": classroom_filter,
        "subject": subject_filter,
        "course": course_filter,
        "group": group_filter,
        "date": date_filter,
        "status": status_filter,
        "weekends": "1" if show_weekends else None,
    }

    active_query_params = {key: value for key, value in base_query_params.items() if value}

    def build_query(month: int, year: int, include_partial: bool = False) -> str:

        params = active_query_params.copy()
        params["month"] = month
        params["year"] = year

        if include_partial:

            params["partial"] = "1"

        return f"?{urlencode(params)}"

    month_label = current_month_start.strftime("%B %Y")
    current_month_entry_count = visible_entry_count

    export_params = active_query_params.copy()
    export_params["month"] = month_value
    export_params["year"] = year_value
    export_querystring = urlencode(export_params)

    month_param_map = {"month": month_value, "year": year_value}

    if show_weekends:

        month_param_map["weekends"] = "1"

    clear_filters_partial_link = urlencode({**month_param_map, "partial": "1"})
    clear_filters_link = urlencode(month_param_map)

    weekend_toggle_params = active_query_params.copy()

    if show_weekends:

        weekend_toggle_params.pop("weekends", None)

    else:

        weekend_toggle_params["weekends"] = "1"

    weekend_toggle_query = urlencode({**weekend_toggle_params, "month": month_value, "year": year_value, "partial": "1"})
    weekend_toggle_plain = urlencode({**weekend_toggle_params, "month": month_value, "year": year_value})

    current_index = year_value * 12 + month_value
    today_index = today.year * 12 + today.month
    visible_offsets = [badge["offset"] for badge in nearby_months]
    min_visible = current_index + (min(visible_offsets) if visible_offsets else 0)
    max_visible = current_index + (max(visible_offsets) if visible_offsets else 0)
    real_month_visible = any(badge["is_current_month"] for badge in nearby_months)
    real_month_direction: Optional[str] = None

    if not real_month_visible:

        if today_index < min_visible:

            real_month_direction = "prev"

        elif today_index > max_visible:

            real_month_direction = "next"

    # Get filter options
    teachers = User.objects.all().order_by('username')
    classrooms = Classroom.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    courses = Course.objects.all().order_by('name')
    groups = ClassGroup.objects.all().order_by('name')

    # Num of entries for the title badge thing
    entry_num = total_entries

    context = {
        'entries': month_entries,
        'entry_num' : entry_num,
        'is_admin' : request.user.is_superuser or request.user.groups.filter(name='admin').exists(),
        'teachers' : teachers,
        'classrooms' : classrooms,
        'subjects' : subjects,
        'courses' : courses,
        'groups' : groups,
        'teacher_filter' : teacher_filter,
        'classroom_filter' : classroom_filter,
        'subject_filter' : subject_filter,
        'course_filter' : course_filter,
        'group_filter' : group_filter,
        'date_filter' : date_filter,
        'status_filter' : status_filter,
        'has_filters' : has_filters,
        'calendar_weeks': calendar_weeks,
        'day_names': day_names,
        'month_label': month_label,
        'current_month': month_value,
        'current_year': year_value,
        'month_navigation': {
            'prev': {
                'month': prev_month,
                'year': prev_year,
                'url': build_query(prev_month, prev_year, include_partial=True),
                'plain_url': build_query(prev_month, prev_year, include_partial=False),
                'label': date(prev_year, prev_month, 1).strftime("%b %Y"),
            },
            'next': {
                'month': next_month,
                'year': next_year,
                'url': build_query(next_month, next_year, include_partial=True),
                'plain_url': build_query(next_month, next_year, include_partial=False),
                'label': date(next_year, next_month, 1).strftime("%b %Y"),
            },
        },
        'month_badges': [
            {
                **badge,
                "url": build_query(badge["month"], badge["year"], include_partial=True),
                "plain_url": build_query(badge["month"], badge["year"], include_partial=False),
            }
            for badge in nearby_months
        ],
        'clear_filters_partial_link': f"?{clear_filters_partial_link}",
        'clear_filters_link': f"?{clear_filters_link}",
        'export_querystring': export_querystring,
        'current_month_link': build_query(month_value, year_value, include_partial=True),
        'current_month_plain_link': build_query(month_value, year_value, include_partial=False),
        'month_entry_count': current_month_entry_count,
        'can_export_entries': current_month_entry_count > 0,
        'has_any_entries': total_entries > 0,
        'show_weekends': show_weekends,
        'weekend_toggle_partial_link': f"?{weekend_toggle_query}",
        'weekend_toggle_link': f"?{weekend_toggle_plain}",
        'calendar_state_token': calendar_state_token,
        'scheduler_updates_url': f"{reverse('scheduler_updates')}{build_query(month_value, year_value, include_partial=False)}",
        'real_month_direction': real_month_direction,
        'status_choices': ScheduleEntry.STATUS_CHOICES,
    }

    return context


@login_required
def scheduler(request: HttpRequest) -> HttpResponse:

    """List schedule entries with filtering, pagination, and active entry flags."""

    context = _build_scheduler_context(request)

    if request.GET.get("partial") == "1":

        return render(request, "core/partials/scheduler_content.html", context)

    return render(request, "core/scheduler.html", context)


@login_required
@require_GET
def scheduler_updates(request: HttpRequest) -> JsonResponse:

    """Return a lightweight JSON payload indicating whether the scheduler changed."""

    client_token = request.GET.get("token")
    context = _build_scheduler_context(request)
    current_token = context.get("calendar_state_token", "0")

    if client_token == current_token:

        return JsonResponse({
            "changed": False,
            "token": current_token,
        })

    html = render_to_string("core/partials/scheduler_content.html", context, request=request)

    return JsonResponse({
        "changed": True,
        "token": current_token,
        "html": html,
    })

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
        group_id = request.POST.get('group')
        date_value = request.POST.get('date')
        start_time_value = request.POST.get('start_time')
        end_time_value = request.POST.get('end_time')

        is_recurring = request.POST.get('is_recurring') == 'on'
        interval_value = request.POST.get('recurrence_interval_days')
        occurrences_value = request.POST.get('recurrence_total_occurrences')
        errors = []
        interval_days: Optional[int] = None
        occurrences: Optional[int] = None

        if not all([teacher_id, classroom_id, subject_id, course_id, group_id, date_value, start_time_value, end_time_value]):

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

        if is_recurring:

            try:

                interval_days = int(interval_value) if interval_value is not None else None

            except (TypeError, ValueError):

                interval_days = None

            if interval_days is None or interval_days <= 0:

                errors.append("Recurring entries require an interval in days greater than zero.")

            try:

                occurrences = int(occurrences_value) if occurrences_value is not None else None

            except (TypeError, ValueError):

                occurrences = None

            if occurrences is None or occurrences < 2:

                errors.append("Recurring entries must repeat at least twice.")

        if errors:

            for message_text in errors:

                flash_messages.error(request, message_text)

            return redirect('scheduler')

        try:

            teacher = User.objects.get(id=teacher_id)
            classroom = Classroom.objects.get(id=classroom_id)
            subject = Subject.objects.get(id=subject_id)
            course = Course.objects.get(id=course_id)
            group = ClassGroup.objects.get(id=group_id)

            with transaction.atomic():

                if is_recurring and interval_days and occurrences:

                    recurrence_group = uuid4()

                    for index in range(occurrences):

                        occurrence_date = entry_date + timedelta(days=interval_days * index)

                        ScheduleEntry.objects.create(
                            teacher=teacher,
                            classroom=classroom,
                            subject=subject,
                            course=course,
                            group=group,
                            date=occurrence_date,
                            start_time=start_time,
                            end_time=end_time,
                            created_by=request.user,
                            recurrence_group=recurrence_group,
                            recurrence_interval_days=interval_days,
                            recurrence_total_occurrences=occurrences,
                            recurrence_index=index + 1
                        )

                    ScheduleEntry.update_recurrence_metadata(recurrence_group)

                    flash_messages.success(
                        request,
                        f"Created {occurrences} recurring schedule entries."
                    )

                else:

                    ScheduleEntry.objects.create(
                        teacher=teacher,
                        classroom=classroom,
                        subject=subject,
                        course=course,
                        group=group,
                        date=entry_date,
                        start_time=start_time,
                        end_time=end_time,
                        created_by=request.user
                    )
                    flash_messages.success(request, "Schedule entry successfully created.")

            return redirect('scheduler')

        except User.DoesNotExist:

            flash_messages.error(request, "Selected teacher not found.")

        except (Classroom.DoesNotExist, Subject.DoesNotExist, Course.DoesNotExist, ClassGroup.DoesNotExist):

            flash_messages.error(request, "Selected item not found.")

        except Exception as error:

            flash_messages.error(request, f"Error creating entry: {str(error)}")

    # Get all data for the form
    teachers = User.objects.all().order_by('username')
    classrooms = Classroom.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    courses = Course.objects.all().order_by('name')
    groups = ClassGroup.objects.all().order_by('name')

    context = {
        'teachers': teachers,
        'classrooms': classrooms,
        'subjects': subjects,
        'courses': courses,
        'groups': groups,
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
        recurrence_count = 1

        if entry.recurrence_group:

            recurrence_count = ScheduleEntry.objects.filter(recurrence_group=entry.recurrence_group).count()

        if request.method == 'POST':

            teacher_id = request.POST.get('teacher')
            classroom_id = request.POST.get('classroom')
            subject_id = request.POST.get('subject')
            course_id = request.POST.get('course')
            group_id = request.POST.get('group')
            date_value = request.POST.get('date')
            start_time_value = request.POST.get('start_time')
            end_time_value = request.POST.get('end_time')
            scope = request.POST.get('recurrence_scope', 'single')
            is_recurring_requested = request.POST.get('is_recurring') == 'on'
            interval_value = request.POST.get('recurrence_interval_days')
            occurrences_value = request.POST.get('recurrence_total_occurrences')

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

            if not all([teacher_id, classroom_id, subject_id, course_id, group_id, date_value, start_time_value, end_time_value]):

                errors.append("All fields are required.")

            if start_time is None:

                errors.append("A valid start time is required.")

            if end_time is None:

                errors.append("A valid end time is required.")

            if start_time and end_time and start_time >= end_time:

                errors.append("End time must be after the start time.")

            interval_days: Optional[int] = None
            occurrences: Optional[int] = None

            if is_recurring_requested:

                try:

                    interval_days = int(interval_value) if interval_value is not None else None

                except (TypeError, ValueError):

                    interval_days = None

                if interval_days is None or interval_days <= 0:

                    errors.append("Recurring entries require an interval in days greater than zero.")

                try:

                    occurrences = int(occurrences_value) if occurrences_value is not None else None

                except (TypeError, ValueError):

                    occurrences = None

                if occurrences is None or occurrences < 2:

                    errors.append("Recurring entries must repeat at least twice.")

            if errors:

                for message_text in errors:

                    flash_messages.error(request, message_text)

                return redirect('scheduler')

            try:

                teacher = User.objects.get(id=teacher_id)
                classroom = Classroom.objects.get(id=classroom_id)
                subject = Subject.objects.get(id=subject_id)
                course = Course.objects.get(id=course_id)
                group = ClassGroup.objects.get(id=group_id)

                apply_to_series = scope == 'series' and entry.recurrence_group and recurrence_count > 1
                existing_group = entry.recurrence_group
                existing_is_recurring = existing_group is not None

                with transaction.atomic():

                    if not existing_is_recurring and not is_recurring_requested:

                        entry.teacher = teacher
                        entry.classroom = classroom
                        entry.subject = subject
                        entry.course = course
                        entry.group = group
                        entry.date = entry_date
                        entry.start_time = start_time
                        entry.end_time = end_time
                        entry.save()

                        flash_messages.success(request, "Schedule entry successfully updated.")

                    elif not existing_is_recurring and is_recurring_requested:

                        recurrence_group = uuid4()

                        entry.teacher = teacher
                        entry.classroom = classroom
                        entry.subject = subject
                        entry.course = course
                        entry.group = group
                        entry.date = entry_date
                        entry.start_time = start_time
                        entry.end_time = end_time
                        entry.recurrence_group = recurrence_group
                        entry.recurrence_interval_days = interval_days
                        entry.recurrence_total_occurrences = occurrences
                        entry.recurrence_index = 1
                        entry.save()

                        for index in range(1, occurrences):

                            occurrence_date = entry_date + timedelta(days=interval_days * index)

                            ScheduleEntry.objects.create(
                                teacher=teacher,
                                classroom=classroom,
                                subject=subject,
                                course=course,
                                group=group,
                                date=occurrence_date,
                                start_time=start_time,
                                end_time=end_time,
                                created_by=request.user,
                                recurrence_group=recurrence_group,
                                recurrence_interval_days=interval_days,
                                recurrence_total_occurrences=occurrences,
                                recurrence_index=index + 1
                            )

                        ScheduleEntry.update_recurrence_metadata(recurrence_group)

                        flash_messages.success(
                            request,
                            f"Schedule series of {occurrences} entries created."
                        )

                    elif existing_is_recurring and not is_recurring_requested:

                        if apply_to_series:

                            series_entries = list(
                                ScheduleEntry.objects.filter(
                                    recurrence_group=existing_group
                                ).order_by("date", "start_time", "id")
                            )

                            original_date = entry.date
                            date_delta = entry_date - original_date

                            for series_entry in series_entries:

                                series_entry.teacher = teacher
                                series_entry.classroom = classroom
                                series_entry.subject = subject
                                series_entry.course = course
                                series_entry.group = group
                                series_entry.start_time = start_time
                                series_entry.end_time = end_time
                                series_entry.date = series_entry.date + date_delta
                                series_entry.recurrence_group = None
                                series_entry.recurrence_interval_days = None
                                series_entry.recurrence_total_occurrences = None
                                series_entry.recurrence_index = None
                                series_entry.save()

                            flash_messages.success(
                                request,
                                "Recurring series converted to individual entries."
                            )

                        else:

                            entry.teacher = teacher
                            entry.classroom = classroom
                            entry.subject = subject
                            entry.course = course
                            entry.group = group
                            entry.date = entry_date
                            entry.start_time = start_time
                            entry.end_time = end_time
                            entry.recurrence_group = None
                            entry.recurrence_interval_days = None
                            entry.recurrence_total_occurrences = None
                            entry.recurrence_index = None
                            entry.save()

                            if existing_group:

                                ScheduleEntry.update_recurrence_metadata(existing_group)

                            flash_messages.success(
                                request,
                                "Schedule entry detached from recurring series."
                            )

                    else:

                        if apply_to_series:

                            ScheduleEntry.update_recurrence_metadata(existing_group)
                            entry.refresh_from_db()

                            series_entries = list(
                                ScheduleEntry.objects.filter(
                                    recurrence_group=existing_group
                                ).order_by("recurrence_index", "date", "start_time", "id")
                            )

                            current_index = entry.recurrence_index or 1
                            new_series_start = entry_date - timedelta(days=interval_days * (current_index - 1))
                            target_dates = [
                                new_series_start + timedelta(days=interval_days * offset)
                                for offset in range(occurrences)
                            ]

                            for index, target_date in enumerate(target_dates):

                                if index < len(series_entries):

                                    series_entry = series_entries[index]
                                    series_entry.teacher = teacher
                                    series_entry.classroom = classroom
                                    series_entry.subject = subject
                                    series_entry.course = course
                                    series_entry.group = group
                                    series_entry.start_time = start_time
                                    series_entry.end_time = end_time
                                    series_entry.date = target_date
                                    series_entry.recurrence_interval_days = interval_days
                                    series_entry.recurrence_total_occurrences = occurrences
                                    series_entry.recurrence_index = index + 1
                                    series_entry.save()

                                else:

                                    ScheduleEntry.objects.create(
                                        teacher=teacher,
                                        classroom=classroom,
                                        subject=subject,
                                        course=course,
                                        group=group,
                                        date=target_date,
                                        start_time=start_time,
                                        end_time=end_time,
                                        created_by=request.user,
                                        recurrence_group=existing_group,
                                        recurrence_interval_days=interval_days,
                                        recurrence_total_occurrences=occurrences,
                                        recurrence_index=index + 1
                                    )

                            if len(series_entries) > occurrences:

                                for extra_entry in series_entries[occurrences:]:

                                    extra_entry.delete()

                            ScheduleEntry.update_recurrence_metadata(existing_group)

                            flash_messages.success(
                                request,
                                f"Schedule series updated to {occurrences} occurrences."
                            )

                        else:

                            entry.teacher = teacher
                            entry.classroom = classroom
                            entry.subject = subject
                            entry.course = course
                            entry.group = group
                            entry.date = entry_date
                            entry.start_time = start_time
                            entry.end_time = end_time
                            entry.save()

                            if existing_group:

                                ScheduleEntry.update_recurrence_metadata(existing_group)

                            flash_messages.success(request, "Schedule entry successfully updated.")

                return redirect('scheduler')

            except User.DoesNotExist:

                flash_messages.error(request, "Selected teacher not found.")

            except (Classroom.DoesNotExist, Subject.DoesNotExist, Course.DoesNotExist, ClassGroup.DoesNotExist):

                flash_messages.error(request, "Selected item not found.")

        # Get all data for the form
        teachers = User.objects.all().order_by('username')
        classrooms = Classroom.objects.all().order_by('name')
        subjects = Subject.objects.all().order_by('name')
        courses = Course.objects.all().order_by('name')
        groups = ClassGroup.objects.all().order_by('name')

        context = {
            'entry' : entry,
            'teachers' : teachers,
            'classrooms': classrooms,
            'subjects': subjects,
            'courses': courses,
            'groups': groups,
            'recurrence_count': recurrence_count,
            'has_recurrence_peers': entry.recurrence_group is not None and recurrence_count > 1,
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

    scope = request.POST.get("scope", "single")
    group_id = entry.recurrence_group
    recurrence_count = 1

    if group_id:

        recurrence_count = ScheduleEntry.objects.filter(recurrence_group=group_id).count()

    delete_series = scope == "series" and group_id and recurrence_count > 1

    with transaction.atomic():

        if delete_series:

            deleted, _ = ScheduleEntry.objects.filter(recurrence_group=group_id).delete()
            message = f"Schedule series of {deleted} entries successfully deleted."

        else:

            entry.delete()

            if group_id:

                ScheduleEntry.update_recurrence_metadata(group_id)

            message = "Schedule entry successfully deleted."

    return ajax_or_redirect(request, True, message, "scheduler")


@login_required
@require_POST
def update_schedule_entry_note(request: HttpRequest) -> HttpResponse:

    """Persist a teacher's private note for a schedule entry."""

    entry_id = request.POST.get("entry_id")

    try:

        entry_pk = int(entry_id)

    except (TypeError, ValueError):

        return ajax_or_redirect(request, False, "Invalid entry identifier.", "scheduler", status_code=400)

    try:

        entry = ScheduleEntry.objects.get(pk=entry_pk)

    except ScheduleEntry.DoesNotExist:

        return ajax_or_redirect(request, False, "Schedule entry not found.", "scheduler", status_code=404)

    if entry.teacher_id != request.user.id:

        return ajax_or_redirect(request, False, "You can only add notes to your own entries.", "scheduler", status_code=403)

    note_text = (request.POST.get("note") or "").strip()
    entry.private_note = note_text
    entry.save(update_fields=["private_note"])

    return ajax_or_redirect(request, True, "Notes saved.", "scheduler")


@login_required
def export_schedule_csv(request: HttpRequest) -> HttpResponse:

    """Export the filtered schedule entries as a CSV attachment."""

    def valid(value: Optional[str]) -> bool:

        return bool(value and value != "None")

    teacher_filter = request.GET.get("teacher")
    classroom_filter = request.GET.get("classroom")
    subject_filter = request.GET.get("subject")
    course_filter = request.GET.get("course")
    group_filter = request.GET.get("group")
    date_filter = request.GET.get("date")
    status_filter = request.GET.get("status")
    month_param = request.GET.get("month")
    year_param = request.GET.get("year")

    valid_status_codes = {code for code, _ in ScheduleEntry.STATUS_CHOICES}

    if status_filter not in valid_status_codes:

        status_filter = None

    queryset = ScheduleEntry.objects.all().select_related(
        "teacher", "classroom", "subject", "course", "group"
    )

    if valid(teacher_filter):

        queryset = queryset.filter(teacher_id=teacher_filter)

    if valid(classroom_filter):

        queryset = queryset.filter(classroom_id=classroom_filter)

    if valid(subject_filter):

        queryset = queryset.filter(subject_id=subject_filter)

    if valid(course_filter):

        queryset = queryset.filter(course_id=course_filter)

    if valid(group_filter):

        queryset = queryset.filter(group_id=group_filter)

    if valid(date_filter):

        queryset = queryset.filter(date=date_filter)

    now = timezone.localtime()
    today = now.date()
    current_time = now.time()
    fallback_date = today

    if status_filter == ScheduleEntry.STATUS_ACTIVE:

        queryset = queryset.filter(
            date=today,
            start_time__lte=current_time,
            end_time__gte=current_time
        )

    elif status_filter == ScheduleEntry.STATUS_UPCOMING:

        queryset = queryset.filter(
            Q(date__gt=today) |
            Q(date=today, start_time__gt=current_time)
        )

    elif status_filter == ScheduleEntry.STATUS_FINISHED:

        queryset = queryset.filter(
            Q(date__lt=today) |
            Q(date=today, end_time__lt=current_time)
        )

    if valid(date_filter):

        try:

            fallback_date = datetime.strptime(date_filter, "%Y-%m-%d").date()

        except (TypeError, ValueError):

            fallback_date = today

    try:

        month_value = int(month_param) if month_param else fallback_date.month
        year_value = int(year_param) if year_param else fallback_date.year

        if month_value < 1 or month_value > 12:

            raise ValueError("Month out of range.")

    except (TypeError, ValueError):

        month_value = fallback_date.month
        year_value = fallback_date.year

    month_start = date(year_value, month_value, 1)
    _, month_days = calendar.monthrange(year_value, month_value)
    month_end = date(year_value, month_value, month_days)

    queryset = queryset.filter(date__gte=month_start, date__lte=month_end)

    show_weekends = request.GET.get("weekends", "0") == "1"

    if not show_weekends:

        queryset = queryset.exclude(date__week_day__in=[1, 7])

    queryset = queryset.order_by("date", "start_time", "id")
    month_entry_count = queryset.count()
    total_entry_count = ScheduleEntry.objects.count()

    if total_entry_count == 0:

        flash_messages.error(
            request,
            "No schedule entries exist yet, so there is nothing to export."
        )
        html = render_to_string("core/partials/scheduler_content.html", {
            "has_any_entries": False,
        }, request=request)
        return JsonResponse({
            "html": html,
            "target": "#scheduler-content"
        })

    if month_entry_count == 0:

        flash_messages.warning(
            request,
            "No schedule entries available to export for the selected month."
        )
        html = render_to_string("core/partials/scheduler_content.html", {
            "has_any_entries": False,
        }, request=request)
        return JsonResponse({
            "html": html,
            "target": "#scheduler-content"
        })

    entries = list(queryset)
    response = HttpResponse(content_type="text/csv")
    filename = f"schedule_{year_value:04d}-{month_value:02d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    writer.writerow([
        "Week",
        "Date",
        "Day",
        "Start Time",
        "End Time",
        "Subject",
        "Course",
        "Teacher",
        "Classroom",
        "Group",
        "Recurring Series",
        "Interval (days)",
        "Status",
        "Personal Note",
    ])

    status_label_map = dict(ScheduleEntry.STATUS_CHOICES)

    for entry in entries:

        classroom_name = getattr(entry.classroom, "display_name", getattr(entry.classroom, "name", ""))
        subject_name = getattr(entry.subject, "display_name", getattr(entry.subject, "name", ""))
        course_name = getattr(entry.course, "display_name", getattr(entry.course, "name", ""))
        group_name = getattr(entry.group, "display_name", getattr(entry.group, "name", "")) if entry.group else ""
        recurrence_label = "N/A"
        interval_label = "N/A"
        status_code = entry.get_status(reference_date=today, reference_time=current_time)
        status_label = status_label_map.get(status_code, status_code.title())
        personal_note = entry.private_note if entry.teacher_id == request.user.id else ""

        if entry.recurrence_group and entry.recurrence_total_occurrences:

            recurrence_label = f"{entry.recurrence_index} of {entry.recurrence_total_occurrences}"

        if entry.recurrence_interval_days:

            interval_label = str(entry.recurrence_interval_days)

        writer.writerow([
            entry.date.isocalendar()[1],
            entry.date.strftime("%Y-%m-%d"),
            entry.date.strftime("%A"),
            entry.start_time.strftime("%H:%M"),
            entry.end_time.strftime("%H:%M"),
            subject_name,
            course_name,
            entry.teacher.username,
            classroom_name,
            group_name,
            recurrence_label,
            interval_label,
            status_label,
            personal_note,
        ])

    return response
