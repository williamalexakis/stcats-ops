# Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file.

from django.contrib import admin
from django.http import HttpRequest
from typing import Any, Iterable
from .models import InviteCode, AuditLog, ScheduleEntry, Classroom, Subject, Course, ClassGroup
from .middleware import log_admin_action

class AuditedModelAdmin(admin.ModelAdmin):

    """Log admin create, update, and delete actions through the audit helper."""

    def save_model(self, request: HttpRequest, obj: Any, form: Any, change: bool) -> None:

        action = "change" if change else "add"

        super().save_model(request, obj, form, change)

        log_admin_action(
            user=request.user,
            action=action,
            obj=obj,
            obj_repr=str(obj),
            extra_data={
                "changed_fields": list(form.changed_data) if hasattr(form, "changed_data") else []
            }
        )

    def delete_model(self, request: HttpRequest, obj: Any) -> None:

        obj_repr = str(obj)

        log_admin_action(
            user=request.user,
            action="delete",
            obj=obj,
            obj_repr=obj_repr
        )

        super().delete_model(request, obj)

    def delete_queryset(self, request: HttpRequest, queryset: Iterable[Any]) -> None:

        for obj in queryset:

            obj_repr = str(obj)

            log_admin_action(
                user=request.user,
                action="delete",
                obj=obj,
                obj_repr=obj_repr
            )

        super().delete_queryset(request, queryset)

class InviteCodeAdmin(AuditedModelAdmin):

    list_display = ("code", "creator", "remaining_uses", "expiration_date", "creation_date")
    list_filter = ("creation_date", "expiration_date")
    search_fields = ("code", "creator__username")
    readonly_fields = ("creator", "creation_date")
    fieldsets = (
        (None, {"fields": ("code", "remaining_uses", "expiration_date")}),
        ("Info", {"fields": ("creator", "creation_date"),"classes": ("collapse",)})
    )

    def save_model(self, request, obj, form, change):

        if not change:

            obj.creator = request.user

        super().save_model(request, obj, form, change)

class ScheduleEntryAdmin(AuditedModelAdmin):

    list_display = ("date", "start_time", "end_time", "teacher", "classroom", "subject", "course", "group", "created_by")
    list_filter = ("date", "classroom", "subject", "course", "group")
    search_fields = ("teacher__username", "subject__display_name", "course__display_name", "group__display_name")
    readonly_fields = ("created_by", "creation_date")

    def save_model(self, request, obj, form, change):

        if not change:

            obj.created_by = request.user

        super().save_model(request, obj, form, change)

class AuditLogAdmin(admin.ModelAdmin):

    list_display = ("creation_date", "actor", "action", "target", "ip")
    list_filter = ("creation_date", "action")
    search_fields = ("actor__username", "action", "target", "ip")
    readonly_fields = ("actor", "action", "target", "ip", "user_agent", "extra", "creation_date")
    fieldsets = (
        ("Action Details", {
            "fields": ("action", "target", "creation_date")
        }),
        ("Actor Information", {
            "fields": ("actor", "ip", "user_agent")
        }),
        ("Additional Data", {
            "fields": ("extra",),
            "classes": ("collapse",)
        })
    )

    def has_add_permission(self, request):

        return False

    def has_change_permission(self, request, obj=None):

        return False

    def has_delete_permission(self, request, obj=None):

        return False

admin.site.register(InviteCode, InviteCodeAdmin)
admin.site.register(ScheduleEntry, ScheduleEntryAdmin)
admin.site.register(AuditLog, AuditLogAdmin)
admin.site.register(Classroom)
admin.site.register(Subject)
admin.site.register(Course)
admin.site.register(ClassGroup)
