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
        related_name="invites_created"
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
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rooms_created"
    )
    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:

        unique_together = [("name")]

class RoomMembership(models.Model):

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="room_memberships"
    )
    join_date = models.DateTimeField(auto_now_add=True)

    class Meta:

        unique_together = [("room", "user")]

class Message(models.Model):

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="messages"
    )
    body = models.TextField()
    creation_date = models.DateTimeField(auto_now_add=True)
    edit_date = models.DateTimeField(null=True, blank=True)
    is_announcement = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)

    class Meta:

        ordering = ["id"]

    def __str__(self):

        preview = self.body[:50]
        return f"{self.author.username}: {preview}..." if len(self.body) > 50 else f"{self.author.username}: {preview}"

class ScheduleEntryManager(models.Manager):

    def cleanup_past_entries(self):

        from django.utils import timezone

        now = timezone.localtime(timezone.now())
        today = now.date()
        current_time = now.time()

        # Delete any expired entries from
        # past dates and today
        deleted_count = self.filter(date__lt=today).delete()[0]
        deleted_count += self.filter(date=today, end_time__lt=current_time).delete()[0]

        return deleted_count

class ScheduleEntry(models.Model):

    ROOM_CHOICES = [
        ("CS1", "CS Lab 1"),
        ("CS2", "CS Lab 2"),
        ("CS3", "CS Lab 3"),
        ("FABLAB", "Fablab")
    ]

    SUBJECT_CHOICES = [
        ("CS", "Computer Science"),
        ("DT", "Design Technology")
    ]

    COURSE_CHOICES = [
        ("GCSE", "GCSE"),
        ("IB", "IB"),
        ("Year 7", "Year 7"),
        ("Year 8", "Year 8"),
        ("Year 9", "Year 9")
    ]

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="schedule_entries"
    )
    room = models.CharField(max_length=50, choices=ROOM_CHOICES)
    subject = models.CharField(max_length=100, choices=SUBJECT_CHOICES)
    course = models.CharField(max_length=50, choices=COURSE_CHOICES)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="schedule_entries_created"
    )
    creation_date = models.DateTimeField(auto_now_add=True)
    objects = ScheduleEntryManager()

    class Meta:

        ordering = ["date", "start_time"]
        verbose_name_plural = "Schedule Entries"

    def __str__(self):

        return f"{self.subject} - {self.teacher.username} - {self.date} {self.start_time}"

    def is_active_now(self):

        from django.utils import timezone

        now = timezone.localtime(timezone.now())
        today = now.date()
        current_time = now.time()

        # Only check entries for today
        if self.date != today:

            return False

        # Check if the current time is within
        # the entry's time range
        return self.start_time <= current_time <= self.end_time

class AuditLog(models.Model):

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=200, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    extra = models.JSONField(default=dict, blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)
