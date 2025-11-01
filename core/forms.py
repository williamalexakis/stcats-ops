from django import forms
from django.contrib.auth.models import Group
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from typing import Optional
from .models import InviteCode

User = get_user_model()

class SignupForm(UserCreationForm):

    invite_code = forms.CharField(max_length=32, help_text="Enter a valid invite code.")

    class Meta:

        model = User
        fields = ("username",)

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

        self._invite_id = invite.pk  # Store the invite PK so we can safely adjust usage when saving

        return code

    @transaction.atomic
    def save(self, commit: bool = True) -> User:

        """Create a user, decrement invite usage, and assign the teacher group."""

        invite: Optional[InviteCode] = None
        invite_id = getattr(self, "_invite_id", None)

        if invite_id is not None:

            try:

                invite = InviteCode.objects.select_for_update().get(pk=invite_id)

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

                invite = None

            else:

                invite.save(update_fields=["remaining_uses"])

        user: User = super().save(commit=commit)

        if not commit:

            return user

        teacher_group = Group.objects.filter(name="teacher").first()

        if teacher_group:

            user.groups.add(teacher_group)

        return user
