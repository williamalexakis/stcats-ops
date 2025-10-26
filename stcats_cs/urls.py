from django.contrib import admin
from django.urls import path
from core.views import (
    home, healthcheck, members, chat,
    admin_panel, delete_invite_code,
    promote_user, demote_user, remove_user,
    edit_message, delete_message,
    scheduler, create_schedule_entry, edit_schedule_entry, delete_schedule_entry
)
from core.views_auth import signup, logout_view
from core.views_announce import announcement_list
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", logout_view, name="logout"),
    path("signup/", signup, name="signup"),
    path("chat/", chat, name="chat"),
    path("chat/message/<int:message_id>/edit/", edit_message, name="edit_message"),
    path("chat/message/<int:message_id>/delete/", delete_message, name="delete_message"),
    path("announcements/", announcement_list, name="announcements"),
    path("members/", members, name="members"),
    path("panel/", admin_panel, name="admin_panel"),
    path("panel/invite/<int:code_id>/delete/", delete_invite_code, name="delete_invite_code"),
    path("members/<int:user_id>/promote/", promote_user, name="promote_user"),
    path("members/<int:user_id>/demote/", demote_user, name="demote_user"),
    path("members/<int:user_id>/remove/", remove_user, name="remove_user"),
    path("scheduler/", scheduler, name="scheduler"),
    path("scheduler/create/", create_schedule_entry, name="create_schedule_entry"),
    path("scheduler/<int:entry_id>/edit/", edit_schedule_entry, name="edit_schedule_entry"),
    path("scheduler/<int:entry_id>/delete/", delete_schedule_entry, name="delete_schedule_entry"),
    path("healthcheck/", healthcheck, name="healthcheck")
]
