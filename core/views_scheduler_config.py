from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash_messages
from django.db.models import ProtectedError
from django.views.decorators.http import require_POST
from typing import Optional
from .models import Classroom, Subject, Course, ClassGroup

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
def admin_scheduler_config(request: HttpRequest) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to access this page.", "home", status_code=403)

    classrooms = Classroom.objects.all().order_by("name")
    subjects = Subject.objects.all().order_by("name")
    courses = Course.objects.all().order_by("name")
    groups = ClassGroup.objects.all().order_by("name")

    context = {
        "classrooms": classrooms,
        "subjects": subjects,
        "courses": courses,
        "groups": groups,
    }

    if request.GET.get("partial") == "1":

        return render(request, "core/partials/admin_scheduler_config.html", context)

    return render(request, "core/admin_scheduler_config.html", context)

@login_required
@require_POST
def add_classroom(request: HttpRequest) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "home", status_code=403)

    name = request.POST.get("name", "").strip()
    display_name = request.POST.get("display_name", "").strip()

    if not name or not display_name:

        return ajax_or_redirect(request, False, "Both name and display name are required.", "admin_scheduler_config", status_code=400)

    if Classroom.objects.filter(name=name).exists():

        return ajax_or_redirect(request, False, f"Classroom '{name}' already exists.", "admin_scheduler_config", status_code=400)

    Classroom.objects.create(
        name=name,
        display_name=display_name,
        created_by=request.user
    )

    return ajax_or_redirect(request, True, f"Classroom '{display_name}' successfully added.", "admin_scheduler_config")

@login_required
@require_POST
def delete_classroom(request: HttpRequest, classroom_id: int) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "home", status_code=403)

    try:

        classroom = Classroom.objects.get(id=classroom_id)

    except Classroom.DoesNotExist:

        return ajax_or_redirect(request, False, "Classroom not found.", "admin_scheduler_config", status_code=404)

    try:

        classroom.delete()

    except ProtectedError:

        return ajax_or_redirect(request, False, f"Cannot delete '{classroom.display_name}' because it's being used in one or more existing entries.", "admin_scheduler_config", status_code=409)

    return ajax_or_redirect(request, True, f"Classroom '{classroom.display_name}' successfully deleted.", "admin_scheduler_config")

@login_required
@require_POST
def add_subject(request: HttpRequest) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "home", status_code=403)

    name = request.POST.get("name", "").strip()
    display_name = request.POST.get("display_name", "").strip()

    if not name or not display_name:

        return ajax_or_redirect(request, False, "Both name and display name are required.", "admin_scheduler_config", status_code=400)

    if Subject.objects.filter(name=name).exists():

        return ajax_or_redirect(request, False, f"Subject '{name}' already exists.", "admin_scheduler_config", status_code=400)

    Subject.objects.create(
        name=name,
        display_name=display_name,
        created_by=request.user
    )

    return ajax_or_redirect(request, True, f"Subject '{display_name}' successfully added.", "admin_scheduler_config")

@login_required
@require_POST
def delete_subject(request: HttpRequest, subject_id: int) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "home", status_code=403)

    try:

        subject = Subject.objects.get(id=subject_id)

    except Subject.DoesNotExist:

        return ajax_or_redirect(request, False, "Subject not found.", "admin_scheduler_config", status_code=404)

    try:

        subject.delete()

    except ProtectedError:

        return ajax_or_redirect(request, False, f"Cannot delete '{subject.display_name}' because it's being used in one or more existing entries.", "admin_scheduler_config", status_code=409)

    return ajax_or_redirect(request, True, f"Subject '{subject.display_name}' successfully deleted.", "admin_scheduler_config")

@login_required
@require_POST
def add_course(request: HttpRequest) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "home", status_code=403)

    name = request.POST.get("name", "").strip()
    display_name = request.POST.get("display_name", "").strip()

    if not name or not display_name:

        return ajax_or_redirect(request, False, "Both name and display name are required.", "admin_scheduler_config", status_code=400)

    if Course.objects.filter(name=name).exists():

        return ajax_or_redirect(request, False, f"Course '{name}' already exists.", "admin_scheduler_config", status_code=400)

    Course.objects.create(
        name=name,
        display_name=display_name,
        created_by=request.user
    )

    return ajax_or_redirect(request, True, f"Course '{display_name}' successfully added.", "admin_scheduler_config")

@login_required
@require_POST
def delete_course(request: HttpRequest, course_id: int) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "home", status_code=403)

    try:

        course = Course.objects.get(id=course_id)

    except Course.DoesNotExist:

        return ajax_or_redirect(request, False, "Course not found.", "admin_scheduler_config", status_code=404)

    try:

        course.delete()

    except ProtectedError:

        return ajax_or_redirect(request, False, f"Cannot delete '{course.display_name}' because it's being used in one or more existing entries.", "admin_scheduler_config", status_code=409)

    return ajax_or_redirect(request, True, f"Course '{course.display_name}' successfully deleted.", "admin_scheduler_config")

@login_required
@require_POST
def add_group(request: HttpRequest) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "home", status_code=403)

    name = request.POST.get("name", "").strip()
    display_name = request.POST.get("display_name", "").strip()

    if not name or not display_name:

        return ajax_or_redirect(request, False, "Both name and display name are required.", "admin_scheduler_config", status_code=400)

    if ClassGroup.objects.filter(name=name).exists():

        return ajax_or_redirect(request, False, f"Group '{name}' already exists.", "admin_scheduler_config", status_code=400)

    ClassGroup.objects.create(
        name=name,
        display_name=display_name,
        created_by=request.user
    )

    return ajax_or_redirect(request, True, f"Group '{display_name}' successfully added.", "admin_scheduler_config")

@login_required
@require_POST
def delete_group(request: HttpRequest, group_id: int) -> HttpResponse:

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        return ajax_or_redirect(request, False, "You do not have permission to perform this action.", "home", status_code=403)

    try:

        class_group = ClassGroup.objects.get(id=group_id)

    except ClassGroup.DoesNotExist:

        return ajax_or_redirect(request, False, "Group not found.", "admin_scheduler_config", status_code=404)

    try:

        class_group.delete()

    except ProtectedError:

        return ajax_or_redirect(request, False, f"Cannot delete '{class_group.display_name}' because it's being used in one or more existing entries.", "admin_scheduler_config", status_code=409)

    return ajax_or_redirect(request, True, f"Group '{class_group.display_name}' successfully deleted.", "admin_scheduler_config")
