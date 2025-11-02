from django.db import models
from django.conf import settings
from django.utils import timezone
from typing import Optional

User = settings.AUTH_USER_MODEL

class InviteCodeManager(models.Manager):

    def cleanup_invalid(self) -> int:

        """Delete expired invite codes and those without remaining uses."""

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

    def is_valid(self) -> bool:

        if self.expiration_date and self.expiration_date < timezone.now():

            return False

        return self.remaining_uses > 0

    def __str__(self) -> str:

        return f"{self.code} ({self.remaining_uses} use(s) left)"

class Classroom(models.Model):

    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="classrooms_created"
    )
    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:

        ordering = ["name"]

    def __str__(self) -> str:

        return self.display_name

class Subject(models.Model):

    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="subjects_created"
    )
    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:

        ordering = ["name"]

    def __str__(self) -> str:

        return self.display_name

class Course(models.Model):

    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="courses_created"
    )
    creation_date = models.DateTimeField(auto_now_add=True)

    class Meta:

        ordering = ["name"]

    def __str__(self) -> str:

        return self.display_name

class ScheduleEntryManager(models.Manager):

    def cleanup_past_entries(self) -> int:

        """Delete schedule entries that ended before now and return the number removed."""

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

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="schedule_entries"
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.PROTECT,
        related_name="schedule_entries"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="schedule_entries"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="schedule_entries"
    )
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

    def __str__(self) -> str:

        return f"{self.subject.display_name} - {self.teacher.username} - {self.date} {self.start_time}"

    @property
    def room(self) -> Optional[str]:

        return self.classroom.name if self.classroom else None

    def is_active_now(self) -> bool:

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

    class Meta:

        ordering = ["-creation_date"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self) -> str:

        actor_name = self.actor.username if self.actor else "System"

        return f"{actor_name} - {self.action} - {self.creation_date.strftime('%Y-%m-%d %H:%M')}"

    def get_action_display(self) -> str:

        action_map = {
            "admin.add": "Created",
            "admin.change": "Modified",
            "admin.delete": "Deleted",
            "http.post": "Submitted Form",
            "admin.action": "Admin Action",
        }

        return action_map.get(self.action, self.action.replace("_", " ").title())

    def get_target_display(self) -> str:

        if not self.target:
            return "N/A"

        # If target is a model reference
        if ":" in self.target:

            parts = self.target.split(":")

            if len(parts) == 2:

                model_path = parts[0]
                obj_id = parts[1]

                # Get only the model name
                if "." in model_path:

                    model_name = model_path.split(".")[-1]

                    return f"{model_name.title()} #{obj_id}"

        # If it's a URL path
        if self.target.startswith("/"):

            return self.target

        return self.target

    def get_object_repr(self) -> Optional[str]:

        if self.extra and "object" in self.extra:

            return self.extra["object"]

        return None
