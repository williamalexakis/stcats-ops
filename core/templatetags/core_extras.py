from django import template

register = template.Library()


@register.filter
def has_group(user, group_name):
    """
    Return True if the user belongs to the group with the provided name.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    return user.groups.filter(name=group_name).exists()


@register.filter
def is_admin(user):
    """
    Determine whether the user is a superuser or belongs to the admin group.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    return user.groups.filter(name="admin").exists()
