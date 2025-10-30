from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash_messages
from django.db.models import ProtectedError
from .models import Classroom, Subject, Course

@login_required
def admin_scheduler_config(request):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to access this page.")

        return redirect("home")

    classrooms = Classroom.objects.all().order_by("name")
    subjects = Subject.objects.all().order_by("name")
    courses = Course.objects.all().order_by("name")

    context = {
        "classrooms": classrooms,
        "subjects": subjects,
        "courses": courses,
    }

    return render(request, "core/admin_scheduler_config.html", context)

@login_required
def add_classroom(request):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("home")

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        display_name = request.POST.get("display_name", "").strip()

        if name and display_name:

            if Classroom.objects.filter(name=name).exists():

                flash_messages.error(request, f"Classroom '{name}' already exists.")

            else:

                Classroom.objects.create(
                    name=name,
                    display_name=display_name,
                    created_by=request.user
                )
                flash_messages.success(request, f"Classroom '{display_name}' successfully added.")

        else:

            flash_messages.error(request, "Both name and display name are required.")

    return redirect("admin_scheduler_config")

@login_required
def delete_classroom(request, classroom_id):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("home")

    try:

        classroom = Classroom.objects.get(id=classroom_id)

        classroom.delete()
        flash_messages.success(request, f"Classroom '{classroom.display_name}' successfully deleted.")

    except Classroom.DoesNotExist:

        flash_messages.error(request, "Classroom not found.")

    except ProtectedError:

        flash_messages.error(request, f"Cannot delete '{classroom.display_name}' because it's being used in one or more existing entries.")

    return redirect("admin_scheduler_config")

@login_required
def add_subject(request):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("home")

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        display_name = request.POST.get("display_name", "").strip()

        if name and display_name:

            if Subject.objects.filter(name=name).exists():

                flash_messages.error(request, f"Subject '{name}' already exists.")

            else:

                Subject.objects.create(
                    name=name,
                    display_name=display_name,
                    created_by=request.user
                )
                flash_messages.success(request, f"Subject '{display_name}' successfully added.")

        else:

            flash_messages.error(request, "Both name and display name are required.")

    return redirect("admin_scheduler_config")

@login_required
def delete_subject(request, subject_id):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("home")

    try:

        subject = Subject.objects.get(id=subject_id)

        subject.delete()
        flash_messages.success(request, f"Subject '{subject.display_name}' successfully deleted.")

    except Subject.DoesNotExist:

        flash_messages.error(request, "Subject not found.")

    except ProtectedError:

        flash_messages.error(request, f"Cannot delete '{subject.display_name}' because it's being used in one or more existing entries.")

    return redirect("admin_scheduler_config")

@login_required
def add_course(request):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("home")

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        display_name = request.POST.get("display_name", "").strip()

        if name and display_name:

            if Course.objects.filter(name=name).exists():

                flash_messages.error(request, f"Course '{name}' already exists.")

            else:

                Course.objects.create(
                    name=name,
                    display_name=display_name,
                    created_by=request.user
                )
                flash_messages.success(request, f"Course '{display_name}' successfully added.")

        else:

            flash_messages.error(request, "Both name and display name are required.")

    return redirect("admin_scheduler_config")

@login_required
def delete_course(request, course_id):

    if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()):

        flash_messages.error(request, "You don't have permission to perform this action.")

        return redirect("home")

    try:

        course = Course.objects.get(id=course_id)

        course.delete()
        flash_messages.success(request, f"Course '{course.display_name}' successfully deleted.")

    except Course.DoesNotExist:

        flash_messages.error(request, "Course not found.")

    except ProtectedError:

        flash_messages.error(request, f"Cannot delete '{course.display_name}' because it's being used in one or more existing entries.")

    return redirect("admin_scheduler_config")
