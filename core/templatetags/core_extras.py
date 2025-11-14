# Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file.

from django import template
from typing import Any

from core.utils.user_display import get_display_initial, get_display_name

register = template.Library()

@register.filter
def has_group(user: Any, group_name: str) -> bool:

    """Return True if the user belongs to the group with the provided name."""

    if not getattr(user, "is_authenticated", False):

        return False

    return user.groups.filter(name=group_name).exists()

@register.filter
def is_admin(user: Any) -> bool:

    """Determine whether the user is a superuser or belongs to the admin group."""

    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    return user.groups.filter(name="admin").exists()

@register.filter
def display_name(user: Any) -> str:

    """Return the user's preferred display name."""

    return get_display_name(user)

@register.filter
def display_initial(user: Any) -> str:

    """Return the first initial derived from the display name."""

    return get_display_initial(user)
