from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone
from django.urls import reverse
from core.forms import SignupForm, SSOSignupForm
from core.middleware import AuditMiddleware, log_admin_action
from core.models import (
    AuditLog,
    Classroom,
    ClassGroup,
    Course,
    InviteCode,
    ScheduleEntry,
    Subject,
)
from core.templatetags.core_extras import has_group, is_admin
from datetime import datetime, date, time, timedelta
import uuid
from unittest import mock
import csv

User = get_user_model()

class InviteCodeTests(TestCase):

    """Test invite code helpers for validation and cleanup."""

    def setUp(self) -> None:

        """Create a reusable user for invite code ownership."""

        self.creator = User.objects.create_user(
            username="creator",
            password="Testpass123!"
        )

    def test_cleanup_invalid_removes_expired_and_unused_codes(self) -> None:

        """Delete expired invite codes and those without remaining uses."""

        now = timezone.now()
        valid_code = InviteCode.objects.create(
            code="valid-code",
            creator=self.creator,
            expiration_date=now + timedelta(days=1),
            remaining_uses=2
        )
        expired_code = InviteCode.objects.create(
            code="expired-code",
            creator=self.creator,
            expiration_date=now - timedelta(days=1),
            remaining_uses=3
        )
        consumed_code = InviteCode.objects.create(
            code="consumed-code",
            creator=self.creator,
            expiration_date=now + timedelta(days=1),
            remaining_uses=0
        )

        deleted = InviteCode.objects.cleanup_invalid()

        self.assertEqual(deleted, 2)
        self.assertTrue(InviteCode.objects.filter(pk=valid_code.pk).exists())
        self.assertFalse(InviteCode.objects.filter(pk=expired_code.pk).exists())
        self.assertFalse(InviteCode.objects.filter(pk=consumed_code.pk).exists())

    def test_is_valid_returns_true_when_not_expired_and_with_uses(self) -> None:

        """Return True for valid invite codes."""

        invite = InviteCode.objects.create(
            code="fresh-code",
            creator=self.creator,
            expiration_date=timezone.now() + timedelta(days=2),
            remaining_uses=1
        )

        self.assertTrue(invite.is_valid())

    def test_is_valid_returns_false_when_expired(self) -> None:

        """Return False for expired invite codes."""

        invite = InviteCode.objects.create(
            code="old-code",
            creator=self.creator,
            expiration_date=timezone.now() - timedelta(minutes=1),
            remaining_uses=5
        )

        self.assertFalse(invite.is_valid())

    def test_is_valid_returns_false_when_no_remaining_uses(self) -> None:

        """Return False when an invite code has no remaining uses."""

        invite = InviteCode.objects.create(
            code="empty-code",
            creator=self.creator,
            remaining_uses=0
        )

        self.assertFalse(invite.is_valid())

class SignupFormTests(TestCase):

    """Test the signup form invite flow and side effects."""

    def setUp(self) -> None:

        """Create a valid invite creator and ensure the teacher group exists."""

        self.invite_creator = User.objects.create_user(
            username="inviter",
            password="Testpass123!"
        )
        Group.objects.create(name="teacher")

    def test_clean_invite_code_rejects_unknown_code(self) -> None:

        """Reject invite codes that do not exist."""

        form = SignupForm(
            data={
                "username": "alice",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
                "invite_code": "missing",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("invite_code", form.errors)

    def test_clean_invite_code_rejects_expired_code(self) -> None:

        """Reject invite codes that are past their expiration date."""

        InviteCode.objects.create(
            code="expired",
            creator=self.invite_creator,
            expiration_date=timezone.now() - timedelta(days=1),
            remaining_uses=1
        )
        form = SignupForm(
            data={
                "username": "bob",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
                "invite_code": "expired",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("invite_code", form.errors)

    def test_clean_invite_code_rejects_consumed_code(self) -> None:

        """Reject invite codes with no remaining uses."""

        InviteCode.objects.create(
            code="used-up",
            creator=self.invite_creator,
            remaining_uses=0
        )
        form = SignupForm(
            data={
                "username": "charlie",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
                "invite_code": "used-up",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("invite_code", form.errors)

    def test_save_decrements_remaining_uses_and_assigns_group(self) -> None:

        """Decrement invite usage and assign the teacher group on signup."""

        invite = InviteCode.objects.create(
            code="enroll",
            creator=self.invite_creator,
            expiration_date=timezone.now() + timedelta(days=2),
            remaining_uses=2
        )
        form = SignupForm(
            data={
                "username": "diana",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
                "invite_code": "enroll",
            }
        )
        self.assertTrue(form.is_valid())

        user = form.save()
        invite.refresh_from_db()

        self.assertEqual(invite.remaining_uses, 1)
        self.assertTrue(user.groups.filter(name="teacher").exists())

class SSOSignupFormTests(TestCase):

    """Test the Microsoft SSO signup helper form."""

    def setUp(self) -> None:

        """Create shared invite and teacher group."""

        self.invite_creator = User.objects.create_user(
            username="microsoft-inviter",
            password="Testpass123!"
        )
        self.invite = InviteCode.objects.create(
            code="microsoft-invite",
            creator=self.invite_creator,
            remaining_uses=1
        )
        Group.objects.create(name="teacher")

    def test_rejects_existing_username(self) -> None:

        """Prevent creating an account when the username already exists."""

        User.objects.create_user(
            username="existing-user",
            password="Testpass123!"
        )
        form = SSOSignupForm(
            data={
                "username": "existing-user",
                "invite_code": self.invite.code
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_save_creates_unusable_password_user_and_consumes_invite(self) -> None:

        """Create an SSO-backed user and remove invite usage."""

        form = SSOSignupForm(
            data={
                "username": "new-sso-user",
                "invite_code": self.invite.code
            }
        )
        self.assertTrue(form.is_valid())

        user = form.save(email="new-sso-user@example.com", extra_fields={"first_name": "New"})

        self.assertEqual(user.email, "new-sso-user@example.com")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.groups.filter(name="teacher").exists())
        self.assertFalse(InviteCode.objects.filter(code=self.invite.code).exists())

    def test_save_deletes_invite_when_usage_exhausted(self) -> None:

        """Delete the invite when the last usage is consumed."""

        invite = InviteCode.objects.create(
            code="last-use",
            creator=self.invite_creator,
            remaining_uses=1
        )
        form = SignupForm(
            data={
                "username": "eve",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
                "invite_code": "last-use",
            }
        )
        self.assertTrue(form.is_valid())

        user = form.save()

        self.assertFalse(InviteCode.objects.filter(pk=invite.pk).exists())
        self.assertTrue(user.groups.filter(name="teacher").exists())

class ScheduleEntryTests(TestCase):

    """Test scheduling helper methods for entries."""

    def setUp(self) -> None:

        """Create the shared teacher, creator, and related objects."""

        self.teacher = User.objects.create_user(
            username="teacher",
            password="Testpass123!"
        )
        self.creator = User.objects.create_user(
            username="creator2",
            password="Testpass123!"
        )
        self.classroom = Classroom.objects.create(
            name="room-101",
            display_name="Room 101",
            created_by=self.creator
        )
        self.subject = Subject.objects.create(
            name="math",
            display_name="Mathematics",
            created_by=self.creator
        )
        self.course = Course.objects.create(
            name="calc",
            display_name="Calculus",
            created_by=self.creator
        )
        self.group = ClassGroup.objects.create(
            name="g1",
            display_name="Group 1",
            created_by=self.creator
        )

    @mock.patch("django.utils.timezone.now")
    def test_cleanup_past_entries_removes_old_entries(self, mocked_now: mock.Mock) -> None:

        """Remove historic entries but preserve those that are still active or upcoming."""

        reference = timezone.make_aware(datetime(2024, 1, 10, 12, 0))
        mocked_now.return_value = reference

        past_entry = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=reference.date() - timedelta(days=1),
            start_time=time(8, 0),
            end_time=time(9, 0),
            created_by=self.creator
        )
        earlier_today = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=reference.date(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            created_by=self.creator
        )
        later_today = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=reference.date(),
            start_time=time(13, 0),
            end_time=time(14, 0),
            created_by=self.creator
        )
        future_entry = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=reference.date() + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(10, 0),
            created_by=self.creator
        )

        deleted = ScheduleEntry.objects.cleanup_past_entries()

        self.assertEqual(deleted, 2)
        self.assertFalse(ScheduleEntry.objects.filter(pk=past_entry.pk).exists())
        self.assertFalse(ScheduleEntry.objects.filter(pk=earlier_today.pk).exists())
        self.assertTrue(ScheduleEntry.objects.filter(pk=later_today.pk).exists())
        self.assertTrue(ScheduleEntry.objects.filter(pk=future_entry.pk).exists())

    @mock.patch("django.utils.timezone.now")
    def test_is_active_now_only_true_for_current_time_window(self, mocked_now: mock.Mock) -> None:

        """Return True only when the current time falls within the entry window."""

        reference = timezone.make_aware(datetime(2024, 5, 1, 11, 0))
        mocked_now.return_value = reference

        entry = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=reference.date(),
            start_time=time(10, 0),
            end_time=time(12, 0),
            created_by=self.creator
        )

        self.assertTrue(entry.is_active_now())

        entry.start_time = time(12, 1)
        entry.end_time = time(13, 0)

        self.assertFalse(entry.is_active_now())

    def test_room_property_returns_classroom_name(self) -> None:

        """Expose the classroom name via the convenience property."""

        entry = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=timezone.now().date(),
            start_time=time(8, 0),
            end_time=time(9, 0),
            created_by=self.creator
        )

        self.assertEqual(entry.room, "room-101")

    def test_update_recurrence_metadata_reindexes_entries(self) -> None:

        """Recalculate recurrence indexes and totals after entries are removed."""

        group_id = uuid.uuid4()
        base_date = timezone.now().date()

        entries = [
            ScheduleEntry.objects.create(
                teacher=self.teacher,
                classroom=self.classroom,
                subject=self.subject,
                course=self.course,
                group=self.group,
                date=base_date + timedelta(days=days),
                start_time=time(8, 0),
                end_time=time(9, 0),
                created_by=self.creator,
                recurrence_group=group_id,
                recurrence_interval_days=7,
                recurrence_total_occurrences=3,
                recurrence_index=index + 1,
            )
            for index, days in enumerate([0, 7, 14])
        ]

        entries[1].delete()

        ScheduleEntry.update_recurrence_metadata(group_id)

        remaining = list(
            ScheduleEntry.objects.filter(recurrence_group=group_id).order_by("date")
        )

        self.assertEqual(len(remaining), 2)
        self.assertEqual([entry.recurrence_index for entry in remaining], [1, 2])
        self.assertTrue(all(entry.recurrence_total_occurrences == 2 for entry in remaining))

class EditScheduleEntryViewTests(TestCase):

    """Verify recurring series logic within the edit schedule entry view."""

    def setUp(self) -> None:

        self.admin = User.objects.create_user(
            username="admin",
            password="Testpass123!",
            is_superuser=True
        )
        self.teacher = User.objects.create_user(
            username="teacher",
            password="Testpass123!"
        )
        self.classroom = Classroom.objects.create(
            name="room-201",
            display_name="Room 201",
            created_by=self.admin
        )
        self.subject = Subject.objects.create(
            name="math",
            display_name="Mathematics",
            created_by=self.admin
        )
        self.course = Course.objects.create(
            name="algebra",
            display_name="Algebra",
            created_by=self.admin
        )
        self.group = ClassGroup.objects.create(
            name="g2",
            display_name="Group 2",
            created_by=self.admin
        )
        self.client.force_login(self.admin)

    def _base_entry(self, date_value: date, start: time, end: time) -> ScheduleEntry:

        return ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=date_value,
            start_time=start,
            end_time=end,
            created_by=self.admin
        )

    def test_edit_can_convert_single_entry_to_recurring_series(self) -> None:

        entry = self._base_entry(datetime(2024, 1, 1).date(), time(9, 0), time(10, 0))

        response = self.client.post(
            reverse("edit_schedule_entry", args=[entry.id]),
            {
                "teacher": str(self.teacher.id),
                "classroom": str(self.classroom.id),
                "subject": str(self.subject.id),
                "course": str(self.course.id),
                "group": str(self.group.id),
                "date": "2024-01-01",
                "start_time": "09:00",
                "end_time": "10:00",
                "is_recurring": "on",
                "recurrence_interval_days": "7",
                "recurrence_total_occurrences": "3",
            },
        )

        self.assertEqual(response.status_code, 302)

        entry.refresh_from_db()
        self.assertIsNotNone(entry.recurrence_group)
        self.assertEqual(entry.recurrence_index, 1)
        self.assertEqual(entry.recurrence_total_occurrences, 3)
        self.assertEqual(entry.recurrence_interval_days, 7)

        series_entries = list(
            ScheduleEntry.objects.filter(
                recurrence_group=entry.recurrence_group
            ).order_by("recurrence_index")
        )

        self.assertEqual(len(series_entries), 3)
        self.assertEqual(
            [occurrence.date for occurrence in series_entries],
            [
                datetime(2024, 1, 1).date(),
                datetime(2024, 1, 8).date(),
                datetime(2024, 1, 15).date(),
            ],
        )

    def test_edit_series_updates_recurrence_settings(self) -> None:

        recurrence_group = uuid.uuid4()
        base_date = datetime(2024, 2, 5).date()

        entries = [
            ScheduleEntry.objects.create(
                teacher=self.teacher,
                classroom=self.classroom,
                subject=self.subject,
                course=self.course,
                group=self.group,
                date=base_date + timedelta(days=7 * index),
                start_time=time(9, 0),
                end_time=time(10, 0),
                created_by=self.admin,
                recurrence_group=recurrence_group,
                recurrence_interval_days=7,
                recurrence_total_occurrences=3,
                recurrence_index=index + 1,
            )
            for index in range(3)
        ]

        response = self.client.post(
            reverse("edit_schedule_entry", args=[entries[0].id]),
            {
                "teacher": str(self.teacher.id),
                "classroom": str(self.classroom.id),
                "subject": str(self.subject.id),
                "course": str(self.course.id),
                "group": str(self.group.id),
                "date": base_date.strftime("%Y-%m-%d"),
                "start_time": "09:00",
                "end_time": "10:00",
                "is_recurring": "on",
                "recurrence_interval_days": "14",
                "recurrence_total_occurrences": "2",
                "recurrence_scope": "series",
            },
        )

        self.assertEqual(response.status_code, 302)

        updated_entries = list(
            ScheduleEntry.objects.filter(
                recurrence_group=recurrence_group
            ).order_by("recurrence_index")
        )

        self.assertEqual(len(updated_entries), 2)
        self.assertTrue(all(entry.recurrence_interval_days == 14 for entry in updated_entries))
        self.assertTrue(all(entry.recurrence_total_occurrences == 2 for entry in updated_entries))
        self.assertEqual(
            [entry.date for entry in updated_entries],
            [
                base_date,
                base_date + timedelta(days=14),
            ],
        )

    def test_edit_can_detach_single_occurrence_from_series(self) -> None:

        recurrence_group = uuid.uuid4()
        base_date = datetime(2024, 3, 1).date()

        series = [
            ScheduleEntry.objects.create(
                teacher=self.teacher,
                classroom=self.classroom,
                subject=self.subject,
                course=self.course,
                group=self.group,
                date=base_date + timedelta(days=7 * index),
                start_time=time(10, 0),
                end_time=time(11, 0),
                created_by=self.admin,
                recurrence_group=recurrence_group,
                recurrence_interval_days=7,
                recurrence_total_occurrences=3,
                recurrence_index=index + 1,
            )
            for index in range(3)
        ]

        response = self.client.post(
            reverse("edit_schedule_entry", args=[series[1].id]),
            {
                "teacher": str(self.teacher.id),
                "classroom": str(self.classroom.id),
                "subject": str(self.subject.id),
                "course": str(self.course.id),
                "group": str(self.group.id),
                "date": (base_date + timedelta(days=7)).strftime("%Y-%m-%d"),
                "start_time": "10:00",
                "end_time": "11:00",
                "recurrence_total_occurrences": "3",
                "recurrence_interval_days": "7",
                "recurrence_scope": "single",
            },
        )

        self.assertEqual(response.status_code, 302)

        series[1].refresh_from_db()
        self.assertIsNone(series[1].recurrence_group)

        remaining = list(
            ScheduleEntry.objects.filter(
                recurrence_group=recurrence_group
            ).order_by("recurrence_index")
        )

        self.assertEqual(len(remaining), 2)
        self.assertTrue(all(entry.recurrence_total_occurrences == 2 for entry in remaining))
        self.assertEqual([entry.recurrence_index for entry in remaining], [1, 2])

class SchedulerCalendarViewTests(TestCase):

    """Ensure the scheduler view builds the calendar-friendly context."""

    def setUp(self) -> None:

        self.viewer = User.objects.create_user(
            username="viewer",
            password="Testpass123!"
        )
        self.teacher = User.objects.create_user(
            username="cal-teacher",
            password="Testpass123!"
        )
        self.classroom = Classroom.objects.create(
            name="cal-room",
            display_name="Calendar Room",
            created_by=self.viewer
        )
        self.subject = Subject.objects.create(
            name="cal-subject",
            display_name="Calendar Subject",
            created_by=self.viewer
        )
        self.course = Course.objects.create(
            name="cal-course",
            display_name="Calendar Course",
            created_by=self.viewer
        )
        self.group = ClassGroup.objects.create(
            name="cal-group",
            display_name="Calendar Group",
            created_by=self.viewer
        )
        self.client.force_login(self.viewer)

    def test_scheduler_calendar_includes_entries_for_month(self) -> None:

        target_date = timezone.now().date() + timedelta(days=5)
        target_month = target_date.month
        target_year = target_date.year

        ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=target_date,
            start_time=time(9, 0),
            end_time=time(10, 0),
            created_by=self.viewer
        )

        response = self.client.get(
            reverse("scheduler"),
            {"month": str(target_month), "year": str(target_year)}
        )

        self.assertEqual(response.status_code, 200)
        calendar_weeks = response.context["calendar_weeks"]
        self.assertEqual(len(response.context["day_names"]), 5)

        entry_found = any(
            day["date"] == target_date and day["entries"]
            for week in calendar_weeks
            for day in week["days"]
        )

        self.assertTrue(entry_found)

        current_badge = next(badge for badge in response.context["month_badges"] if badge["is_current"])
        self.assertEqual(current_badge["count"], 1)

    def test_scheduler_calendar_handles_empty_state(self) -> None:

        response = self.client.get(reverse("scheduler"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_any_entries"])

    def test_scheduler_calendar_shows_weekends_when_requested(self) -> None:

        target_date = timezone.localdate()

        ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=target_date,
            start_time=time(9, 0),
            end_time=time(10, 0),
            created_by=self.viewer
        )

        response = self.client.get(
            reverse("scheduler"),
            {
                "month": str(target_date.month),
                "year": str(target_date.year),
                "weekends": "1",
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["day_names"]), 7)

class ExportScheduleCsvTests(TestCase):

    """Validate CSV export respects calendar month and applied filters."""

    def setUp(self) -> None:

        self.user = User.objects.create_user(
            username="calendar-user",
            password="Testpass123!"
        )
        self.teacher = User.objects.create_user(
            username="csv-teacher",
            password="Testpass123!"
        )
        self.other_teacher = User.objects.create_user(
            username="csv-other",
            password="Testpass123!"
        )
        self.classroom = Classroom.objects.create(
            name="csv-room",
            display_name="CSV Room",
            created_by=self.user
        )
        self.subject = Subject.objects.create(
            name="csv-subject",
            display_name="CSV Subject",
            created_by=self.user
        )
        self.course = Course.objects.create(
            name="csv-course",
            display_name="CSV Course",
            created_by=self.user
        )
        self.group = ClassGroup.objects.create(
            name="csv-group",
            display_name="CSV Group",
            created_by=self.user
        )

        self.client.force_login(self.user)

    def test_export_filters_to_visible_month(self) -> None:

        today = timezone.localdate()
        target_month = today.month
        target_year = today.year
        month_start = date(target_year, target_month, 1)
        calendar_start = month_start - timedelta(days=month_start.weekday())

        primary_entry = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=month_start + timedelta(days=4),
            start_time=time(9, 0),
            end_time=time(10, 0),
            created_by=self.user,
            recurrence_group=uuid.uuid4(),
            recurrence_interval_days=7,
            recurrence_total_occurrences=3,
            recurrence_index=1,
        )

        leading_entry = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=calendar_start,
            start_time=time(12, 0),
            end_time=time(13, 0),
            created_by=self.user
        )

        weekend_entry = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=month_start + timedelta(days=5),
            start_time=time(11, 0),
            end_time=time(12, 0),
            created_by=self.user
        )

        ScheduleEntry.objects.create(
            teacher=self.other_teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=month_start + timedelta(days=10),
            start_time=time(15, 0),
            end_time=time(16, 0),
            created_by=self.user
        )

        response = self.client.get(
            reverse("export_schedule_csv"),
            {
                "month": str(target_month),
                "year": str(target_year),
                "teacher": str(self.teacher.id),
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="schedule_{target_year:04d}-{target_month:02d}.csv"'
        )

        decoded = response.content.decode("utf-8").splitlines()
        reader = csv.reader(decoded)
        rows = list(reader)

        self.assertEqual(len(rows), 1 + 2)
        header = rows[0]
        self.assertIn("Week", header)
        self.assertIn("Recurring Series", header)

        exported_dates = {row[1] for row in rows[1:]}
        self.assertIn(primary_entry.date.strftime("%Y-%m-%d"), exported_dates)
        self.assertIn(leading_entry.date.strftime("%Y-%m-%d"), exported_dates)
        self.assertNotIn(weekend_entry.date.strftime("%Y-%m-%d"), exported_dates)

        recurring_row = next(row for row in rows[1:] if row[1] == primary_entry.date.strftime("%Y-%m-%d"))
        self.assertEqual(recurring_row[10], "1 of 3")
        self.assertEqual(recurring_row[11], "7")

    def test_export_with_no_entries_redirects_with_message(self) -> None:

        today = timezone.localdate()
        response = self.client.get(
            reverse("export_schedule_csv"),
            {
                "month": str(today.month),
                "year": str(today.year),
            },
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.redirect_chain)

        messages = list(response.context["messages"])
        self.assertTrue(any("No schedule entries available to export" in message.message for message in messages))

    def test_export_includes_weekends_when_requested(self) -> None:

        today = timezone.localdate()
        days_until_saturday = (5 - today.weekday()) % 7
        saturday = today + timedelta(days=days_until_saturday)

        entry = ScheduleEntry.objects.create(
            teacher=self.teacher,
            classroom=self.classroom,
            subject=self.subject,
            course=self.course,
            group=self.group,
            date=saturday,
            start_time=time(10, 0),
            end_time=time(11, 0),
            created_by=self.user
        )

        response = self.client.get(
            reverse("export_schedule_csv"),
            {
                "month": str(saturday.month),
                "year": str(saturday.year),
                "weekends": "1",
            }
        )

        self.assertEqual(response.status_code, 200)
        decoded = response.content.decode("utf-8").splitlines()
        rows = list(csv.reader(decoded))
        exported_dates = {row[1] for row in rows[1:]}
        self.assertIn(entry.date.strftime("%Y-%m-%d"), exported_dates)

class AuditLogTests(TestCase):

    """Test display helpers and logging utilities for audit logs."""

    def setUp(self) -> None:

        """Create a reusable actor for audit log entries."""

        self.user = User.objects.create_user(
            username="auditor",
            password="Testpass123!"
        )

    def test_get_action_display_maps_known_actions(self) -> None:

        """Map known action codes to friendly labels."""

        log = AuditLog.objects.create(
            actor=self.user,
            action="admin.add",
            target="",
            user_agent="",
            extra={}
        )

        self.assertEqual(log.get_action_display(), "Created")

    def test_get_action_display_formats_unknown_action(self) -> None:

        """Title-case unknown action codes."""

        log = AuditLog.objects.create(
            actor=self.user,
            action="custom_event",
            target="",
            user_agent="",
            extra={}
        )

        self.assertEqual(log.get_action_display(), "Custom Event")

    def test_get_target_display_for_model_reference(self) -> None:

        """Show a pluralised model label when the target references an object."""

        log = AuditLog.objects.create(
            actor=self.user,
            action="admin.add",
            target="core.invitecode:5",
            user_agent="",
            extra={}
        )

        self.assertEqual(log.get_target_display(), "Invitecode #5")

    def test_get_target_display_for_path(self) -> None:

        """Return the path unchanged when the target is a URL."""

        log = AuditLog.objects.create(
            actor=self.user,
            action="http.post",
            target="/dashboard/",
            user_agent="",
            extra={}
        )

        self.assertEqual(log.get_target_display(), "/dashboard/")

    def test_get_target_display_for_plain_target(self) -> None:

        """Return a literal target string when no special handling is needed."""

        log = AuditLog.objects.create(
            actor=self.user,
            action="http.post",
            target="Manual entry",
            user_agent="",
            extra={}
        )

        self.assertEqual(log.get_target_display(), "Manual entry")

    def test_get_object_repr_returns_extra_object(self) -> None:

        """Return the object representation from the extra payload."""

        log = AuditLog.objects.create(
            actor=self.user,
            action="admin.add",
            target="",
            user_agent="",
            extra={"object": "Invite 123"}
        )

        self.assertEqual(log.get_object_repr(), "Invite 123")

    def test_get_object_repr_returns_none_when_missing(self) -> None:

        """Return None when the extra payload lacks the object key."""

        log = AuditLog.objects.create(
            actor=self.user,
            action="admin.add",
            target="",
            user_agent="",
            extra={}
        )

        self.assertIsNone(log.get_object_repr())

    def test_log_admin_action_creates_entry_with_expected_fields(self) -> None:

        """Persist all metadata when logging an admin action with an object."""

        invite = InviteCode.objects.create(
            code="admin-action",
            creator=self.user,
            remaining_uses=1
        )

        log_admin_action(
            user=self.user,
            action="add",
            obj=invite,
            obj_repr="Invite admin-action",
            extra_data={"note": "details"}
        )

        log = AuditLog.objects.latest("creation_date")
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.action, "admin.add")
        self.assertTrue(log.target.startswith("core.invitecode:"))
        self.assertEqual(log.extra["object"], "Invite admin-action")
        self.assertEqual(log.extra["admin_action"], "add")
        self.assertEqual(log.extra["note"], "details")

    def test_log_admin_action_handles_missing_object(self) -> None:

        """Log admin actions even when no object reference is provided."""

        log_admin_action(user=self.user, action="delete", obj=None)

        log = AuditLog.objects.latest("creation_date")
        self.assertEqual(log.action, "admin.delete")
        self.assertEqual(log.target, "")

class AuditMiddlewareTests(TestCase):

    """Test the audit middleware behavior for various request types."""

    def setUp(self) -> None:

        """Prepare a request factory and authenticated user."""

        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="poster",
            password="Testpass123!"
        )

    def test_post_request_logs_audit_entry(self) -> None:

        """Log standard POST submissions with truncated headers."""

        middleware = AuditMiddleware(lambda request: HttpResponse(status=201))
        request = self.factory.post(
            "/announce/",
            data={"body": "hello"},
            HTTP_USER_AGENT="Agent" * 120,
            REMOTE_ADDR="127.0.0.1"
        )
        request.user = self.user

        response = middleware(request)

        self.assertEqual(response.status_code, 201)
        log = AuditLog.objects.latest("creation_date")

        # The middleware truncates long user agents to 400 characters.
        self.assertEqual(log.actor, self.user)
        self.assertEqual(log.action, "http.post")
        self.assertEqual(log.target, "/announce/")
        self.assertEqual(len(log.user_agent), 400)
        self.assertEqual(log.extra["status"], 201)

    def test_post_request_to_admin_includes_admin_context(self) -> None:

        """Log POST requests to admin URLs with additional context."""

        middleware = AuditMiddleware(lambda request: HttpResponse(status=200))
        request = self.factory.post(
            "/admin/core/invitecode/",
            data={"body": "hello"},
            REMOTE_ADDR="127.0.0.1"
        )
        request.user = self.user
        request.META["HTTP_USER_AGENT"] = "Mozilla"

        middleware(request)

        log = AuditLog.objects.latest("creation_date")
        self.assertEqual(log.action, "admin.action")
        self.assertEqual(log.target, "/admin/core/invitecode/")
        self.assertEqual(log.extra["status"], 200)
        self.assertEqual(log.extra["admin_path"], "/admin/core/invitecode/")

    def test_get_request_does_not_log(self) -> None:

        """Skip logging for non-POST requests."""

        middleware = AuditMiddleware(lambda request: HttpResponse(status=200))
        request = self.factory.get("/announce/")
        request.user = self.user

        middleware(request)

        self.assertFalse(AuditLog.objects.exists())

class TemplateFilterTests(TestCase):

    """Test template filters that check for group membership and admin status."""

    def setUp(self) -> None:

        """Create reusable groups and a baseline user."""

        self.teacher_group = Group.objects.create(name="teacher")
        self.admin_group = Group.objects.create(name="admin")
        self.user = User.objects.create_user(
            username="member",
            password="Testpass123!"
        )

    def test_has_group_returns_true_when_user_in_group(self) -> None:

        """Return True when the user belongs to the requested group."""

        self.user.groups.add(self.teacher_group)

        self.assertTrue(has_group(self.user, "teacher"))

    def test_has_group_returns_false_for_unauthenticated(self) -> None:

        """Return False for anonymous users."""

        anonymous = AnonymousUser()

        self.assertFalse(has_group(anonymous, "teacher"))

    def test_is_admin_returns_true_for_superuser(self) -> None:

        """Return True for superusers."""

        superuser = User.objects.create_superuser(
            username="super",
            email="super@example.com",
            password="Str0ngPass!23"
        )

        self.assertTrue(is_admin(superuser))

    def test_is_admin_returns_true_for_admin_group(self) -> None:

        """Return True when the user belongs to the admin group."""

        self.user.groups.add(self.admin_group)

        self.assertTrue(is_admin(self.user))

    def test_is_admin_returns_false_otherwise(self) -> None:

        """Return False when the user lacks admin privileges."""

        self.assertFalse(is_admin(self.user))
