# Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file.

from django.contrib import admin
from django.urls import include, path
from core.views import (
    home, healthcheck, members,
    admin_dashboard, admin_invites,
    admin_audit_logs, delete_invite_code,
    promote_user, demote_user,
    remove_user, code_editor,
    scheduler, scheduler_updates,
    create_schedule_entry, edit_schedule_entry,
    delete_schedule_entry, export_schedule_csv,
    update_schedule_entry_note
)
from core.views_auth import signup, logout_view, complete_sso_signup, legacy_signup
from core.views_scheduler_config import (
    admin_scheduler_config, add_classroom, delete_classroom,
    add_subject, delete_subject, add_course, delete_course,
    add_group, delete_group
)
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("social_django.urls", namespace="social")),
    path("", home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", logout_view, name="logout"),
    path("signup/", signup, name="signup"),
    path("signup/legacy/", legacy_signup, name="legacy_signup"),
    path("signup/complete/", complete_sso_signup, name="complete_sso_signup"),
    path("members/", members, name="members"),
    path("code-editor/", code_editor, name="code_editor"),
    path("panel/", admin_dashboard, name="admin_dashboard"),
    path("panel/", admin_dashboard, name="admin_panel"),  # Admin invites <-- changing this is too annoying
    path("panel/invites/", admin_invites, name="admin_invites"),
    path("panel/invite/<int:code_id>/delete/", delete_invite_code, name="delete_invite_code"),
    path("members/<int:user_id>/promote/", promote_user, name="promote_user"),
    path("members/<int:user_id>/demote/", demote_user, name="demote_user"),
    path("members/<int:user_id>/remove/", remove_user, name="remove_user"),
    path("scheduler/", scheduler, name="scheduler"),
    path("scheduler/create/", create_schedule_entry, name="create_schedule_entry"),
    path("scheduler/updates/", scheduler_updates, name="scheduler_updates"),
    path("scheduler/<int:entry_id>/edit/", edit_schedule_entry, name="edit_schedule_entry"),
    path("scheduler/<int:entry_id>/delete/", delete_schedule_entry, name="delete_schedule_entry"),
    path("scheduler/note/", update_schedule_entry_note, name="update_schedule_entry_note"),
    path("schedule/export/", export_schedule_csv, name="export_schedule_csv"),
    path("panel/scheduler-config/", admin_scheduler_config, name="admin_scheduler_config"),
    path("panel/scheduler-config/classroom/add/", add_classroom, name="add_classroom"),
    path("panel/scheduler-config/classroom/<int:classroom_id>/delete/", delete_classroom, name="delete_classroom"),
    path("panel/scheduler-config/subject/add/", add_subject, name="add_subject"),
    path("panel/scheduler-config/subject/<int:subject_id>/delete/", delete_subject, name="delete_subject"),
    path("panel/scheduler-config/course/add/", add_course, name="add_course"),
    path("panel/scheduler-config/course/<int:course_id>/delete/", delete_course, name="delete_course"),
    path("panel/scheduler-config/group/add/", add_group, name="add_group"),
    path("panel/scheduler-config/group/<int:group_id>/delete/", delete_group, name="delete_group"),
    path("panel/audit-logs/", admin_audit_logs, name="admin_audit_logs"),
    path("healthcheck/", healthcheck, name="healthcheck")
]
