from typing import Optional

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from .models import InviteCode

User = get_user_model()

class InviteCodeFormMixin:

    def clean_invite_code(self) -> str:

        code = self.cleaned_data["invite_code"].strip()

        try:

            invite: InviteCode = InviteCode.objects.get(code=code)

        except InviteCode.DoesNotExist:

            raise forms.ValidationError("Invalid invite code.")

        if invite.expiration_date and invite.expiration_date < timezone.now():

            raise forms.ValidationError("This invite code has expired.")

        if invite.remaining_uses <= 0:

            raise forms.ValidationError("This invite code has no remaining uses.")

        return code

    def _consume_invite(self) -> None:

        code = self.cleaned_data.get("invite_code")

        if not code:

            raise forms.ValidationError("An invite code must be provided.")

        code = str(code).strip()

        try:

            invite = InviteCode.objects.select_for_update().get(code=code)

        except InviteCode.DoesNotExist:

            raise forms.ValidationError("This invite code is no longer available.")

        now = timezone.now()

        if invite.expiration_date and invite.expiration_date < now:

            invite.delete()

            raise forms.ValidationError("This invite code has expired.")

        if invite.remaining_uses <= 0:

            invite.delete()

            raise forms.ValidationError("This invite code has no remaining uses.")

        invite.remaining_uses -= 1

        if invite.remaining_uses <= 0:

            invite.delete()

        else:

            invite.save(update_fields=["remaining_uses"])

    def _assign_teacher_group(self, user: User) -> None:

        teacher_group = Group.objects.filter(name="teacher").first()

        if teacher_group:

            user.groups.add(teacher_group)


class SignupForm(InviteCodeFormMixin, UserCreationForm):

    invite_code = forms.CharField(max_length=32, help_text="Enter a valid invite code.")

    class Meta:

        model = User
        fields = ("username",)

    @transaction.atomic
    def save(self, commit: bool = True) -> User:

        """Create a user, decrement invite usage, and assign the teacher group."""

        self._consume_invite()

        user: User = super().save(commit=commit)

        if not commit:

            return user

        self._assign_teacher_group(user)

        return user


class SSOSignupForm(InviteCodeFormMixin, forms.Form):

    invite_code = forms.CharField(max_length=32, help_text="Enter a valid invite code.")
    username = forms.CharField(max_length=150)

    def clean_username(self) -> str:

        username = self.cleaned_data["username"]

        if User.objects.filter(username=username).exists():

            raise forms.ValidationError("This username is already taken.")

        return username

    @transaction.atomic
    def save(self, email: str = "", extra_fields: Optional[dict] = None) -> User:

        """Create an SSO-backed user, consume the invite, and assign the teacher group."""

        self._consume_invite()
        cleaned_username = self.cleaned_data["username"]
        extra_fields = extra_fields or {}

        user = User.objects.create_user(
            username=cleaned_username,
            email=email or "",
            password=None,
            **extra_fields
        )
        self._assign_teacher_group(user)

        return user
