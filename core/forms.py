from django import forms
from django.contrib.auth.models import Group
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from .models import InviteCode

User = get_user_model()


class SignupForm(UserCreationForm):
    invite_code = forms.CharField(
        max_length=32, help_text="Enter your invite code from an admin."
    )

    class Meta:
        model = User
        fields = ("username",)

    def clean_invite_code(self):
        code = self.cleaned_data["invite_code"].strip()

        try:
            invite = InviteCode.objects.get(code=code)

        except InviteCode.DoesNotExist:
            raise forms.ValidationError("Invalid invite code.")

        if invite.expiration_date and invite.expiration_date < timezone.now():
            raise forms.ValidationError("This invite has expired.")
        if invite.remaining_uses <= 0:
            raise forms.ValidationError("This invite has no remaining uses.")

        self._invite = invite
        return code

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=commit)

        invite = getattr(self, "_invite", None)

        if invite:
            invite.remaining_uses -= 1
            
            # Delete the invite if it's used up or expired
            if invite.remaining_uses <= 0 or (invite.expiration_date and invite.expiration_date < timezone.now()):
                invite.delete()
            else:
                invite.save(update_fields=["remaining_uses"])

        teacher_group = Group.objects.filter(name="teacher").first()

        if teacher_group:
            user.groups.add(teacher_group)

        return user
