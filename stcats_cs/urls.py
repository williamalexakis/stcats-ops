from django.contrib import admin
from django.urls import include, path
from core.views import (
    home, healthcheck, members, chat,
    admin_dashboard, admin_invites,
    admin_audit_logs, delete_invite_code,
    promote_user, demote_user,
    remove_user, edit_message, code_editor,
    delete_message, scheduler,
    create_schedule_entry, edit_schedule_entry,
    delete_schedule_entry, export_schedule_csv
)
from core.views_auth import signup, logout_view, complete_sso_signup, legacy_signup
from core.views_announce import announcement_list
from core.views_scheduler_config import (
    admin_scheduler_config, add_classroom, delete_classroom,
    add_subject, delete_subject, add_course, delete_course
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
    path("chat/", chat, name="chat"),
    path("chat/message/<int:message_id>/edit/", edit_message, name="edit_message"),
    path("chat/message/<int:message_id>/delete/", delete_message, name="delete_message"),
    path("announcements/", announcement_list, name="announcements"),
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
    path("scheduler/<int:entry_id>/edit/", edit_schedule_entry, name="edit_schedule_entry"),
    path("scheduler/<int:entry_id>/delete/", delete_schedule_entry, name="delete_schedule_entry"),
    path("schedule/export/", export_schedule_csv, name="export_schedule_csv"),
    path("panel/scheduler-config/", admin_scheduler_config, name="admin_scheduler_config"),
    path("panel/scheduler-config/classroom/add/", add_classroom, name="add_classroom"),
    path("panel/scheduler-config/classroom/<int:classroom_id>/delete/", delete_classroom, name="delete_classroom"),
    path("panel/scheduler-config/subject/add/", add_subject, name="add_subject"),
    path("panel/scheduler-config/subject/<int:subject_id>/delete/", delete_subject, name="delete_subject"),
    path("panel/scheduler-config/course/add/", add_course, name="add_course"),
    path("panel/scheduler-config/course/<int:course_id>/delete/", delete_course, name="delete_course"),
    path("panel/audit-logs/", admin_audit_logs, name="admin_audit_logs"),
    path("healthcheck/", healthcheck, name="healthcheck")
]
