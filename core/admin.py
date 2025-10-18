from django.contrib import admin
from .models import InviteCode, Room, RoomMembership, Message, Announcement, AuditLog

admin.site.register([InviteCode, Room, RoomMembership, Message, Announcement, AuditLog])
