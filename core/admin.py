from django.contrib import admin
from .models import InviteCode, Room, RoomMembership, Message, Announcement, AuditLog


class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'creator', 'remaining_uses', 'expiration_date', 'creation_date')
    list_filter = ('creation_date', 'expiration_date')
    search_fields = ('code', 'creator__username')
    readonly_fields = ('creator', 'creation_date')
    
    fieldsets = (
        (None, {
            'fields': ('code', 'remaining_uses', 'expiration_date')
        }),
        ('Info', {
            'fields': ('creator', 'creation_date'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set creator when creating new invite code
            obj.creator = request.user
        super().save_model(request, obj, form, change)


admin.site.register(InviteCode, InviteCodeAdmin)
admin.site.register([Room, RoomMembership, Message, Announcement, AuditLog])