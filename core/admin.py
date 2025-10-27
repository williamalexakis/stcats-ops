from django.contrib import admin
from .models import InviteCode, Room, RoomMembership, Message, AuditLog, ScheduleEntry, Classroom, Subject, Course
from .middleware import log_admin_action

class AuditedModelAdmin(admin.ModelAdmin):

    def save_model(self, request, obj, form, change):

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

    def delete_model(self, request, obj):

        obj_repr = str(obj)

        log_admin_action(
            user=request.user,
            action="delete",
            obj=obj,
            obj_repr=obj_repr
        )

        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):

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

class RoomAdmin(AuditedModelAdmin):

    list_display = ("name", "is_private", "creator", "creation_date")
    list_filter = ("is_private", "creation_date")
    search_fields = ("name", "creator__username")
    readonly_fields = ("creator", "creation_date")

class RoomMembershipAdmin(AuditedModelAdmin):

    list_display = ("room", "user", "join_date")
    list_filter = ("join_date", "room")
    search_fields = ("room__name", "user__username")
    readonly_fields = ("join_date",)

class MessageAdmin(AuditedModelAdmin):

    list_display = ("room", "author", "body_preview", "is_announcement", "is_pinned", "creation_date", "edit_date")
    list_filter = ("is_announcement", "is_pinned", "creation_date", "room")
    search_fields = ("author__username", "body", "room__name")
    readonly_fields = ("creation_date", "edit_date")

    def body_preview(self, obj):

        return obj.body[:50] + ("..." if len(obj.body) > 50 else "")

    body_preview.short_description = "Message Preview"

class ScheduleEntryAdmin(AuditedModelAdmin):

    list_display = ("date", "start_time", "end_time", "teacher", "classroom", "subject", "course", "created_by")
    list_filter = ("date", "classroom", "subject", "course")
    search_fields = ("teacher__username", "subject", "course")
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
admin.site.register(Room, RoomAdmin)
admin.site.register(RoomMembership, RoomMembershipAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(ScheduleEntry, ScheduleEntryAdmin)
admin.site.register(AuditLog, AuditLogAdmin)
admin.site.register(Classroom)
admin.site.register(Subject)
admin.site.register(Course)
