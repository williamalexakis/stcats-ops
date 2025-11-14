# Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file.

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import UserProfile

User = get_user_model()

@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):

    """Create or fetch a profile each time a user record is saved."""

    if not instance:

        return

    if created:

        UserProfile.objects.create(user=instance)

    else:

        UserProfile.objects.get_or_create(user=instance)
