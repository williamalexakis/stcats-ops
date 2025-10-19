from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class InviteCodeManager(models.Manager):

    def cleanup_invalid(self):

        now = timezone.now()
        deleted_count = self.filter(remaining_uses__lte=0).delete()[0]
        deleted_count += self.filter(expiration_date__lt=now).delete()[0]

        return deleted_count


class InviteCode(models.Model):

    code = models.CharField(max_length=32, unique=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="invites_created",
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    expiration_date = models.DateTimeField(null=True, blank=True)
    remaining_uses = models.PositiveIntegerField(default=1)

    objects = InviteCodeManager()

    def is_valid(self):
        if self.expiration_date and self.expiration_date < timezone.now():
            return False

        return self.remaining_uses > 0

    def __str__(self):
        return f"{self.code} ({self.remaining_uses} use(s) left)"


class Room(models.Model):
    name = models.CharField(max_length=80)
    is_private = models.BooleanField(default=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rooms_created"
    )
    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("name",)]


class RoomMembership(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="room_memberships",
    )
    join_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("room", "user")]


class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="messages"
    )
    body = models.TextField()
    creation_date = models.DateTimeField(auto_now_add=True)
    edit_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creation_date = models.DateTimeField(auto_now_add=True)
    pinned = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=200, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    extra = models.JSONField(default=dict, blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)
