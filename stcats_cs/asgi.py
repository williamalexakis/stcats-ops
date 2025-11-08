# Copyright © William Alexakis. All Rights Reserved. Use governed by LICENSE file.

"""
ASGI config for stcats_cs project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stcats_cs.settings')

application = get_asgi_application()
