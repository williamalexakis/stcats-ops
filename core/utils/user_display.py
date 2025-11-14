# Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file.

from __future__ import annotations
from django.contrib.auth import get_user_model
from core.models import UserProfile
from typing import Optional

UserModel = get_user_model()

def _ensure_profile(user: UserModel) -> Optional[UserProfile]:

    if not user or not getattr(user, "pk", None):

        return None

    profile = getattr(user, "profile", None)

    if profile:

        return profile

    profile, _ = UserProfile.objects.get_or_create(user=user)

    return profile

def get_display_name(user: Optional[UserModel]) -> str:

    if not user:

        return ""

    profile = _ensure_profile(user)

    if profile and profile.display_name:

        return profile.display_name

    return user.get_username()

def get_display_initial(user: Optional[UserModel]) -> str:

    name = get_display_name(user) or (user.get_username() if user else "")

    if not name:

        return "?"

    return name.strip()[0].upper()
