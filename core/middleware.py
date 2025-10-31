from typing import Any, Callable, Dict, Optional
from django.http import HttpRequest, HttpResponse
from .models import AuditLog
from django.contrib.contenttypes.models import ContentType

class AuditMiddleware:

    """Log POST requests and admin actions into the audit log."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:

        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:

        response: HttpResponse = self.get_response(request)

        try:

            if request.method == "POST":

                # Get the actor
                actor: Optional[Any] = None

                if hasattr(request, "user") and request.user.is_authenticated:

                    actor = request.user

                # Get user agent and truncate it if needed
                user_agent = request.META.get("HTTP_USER_AGENT", "")[:400]
                action = "http.post"  # Determine the action type
                extra = {"status": response.status_code}

                # Add more context for admin actions
                if request.path.startswith("/admin/"):

                    action = "admin.action"
                    extra["admin_path"] = request.path[:200]

                AuditLog.objects.create(
                    actor=actor,
                    action=action,
                    target=request.path[:200],
                    ip=request.META.get("REMOTE_ADDR"),
                    user_agent=user_agent,
                    extra=extra
                )

        # Do nothing to prevent request interruption
        except Exception:

            pass

        return response

def log_admin_action(
    user: Optional[Any],
    action: str,
    obj: Optional[Any] = None,
    obj_repr: Optional[str] = None,
    extra_data: Optional[Dict[str, Any]] = None,
) -> None:

    """Record an admin action in the audit log with optional metadata."""

    try:

        target = ""
        extra: Dict[str, Any] = extra_data or {}

        if obj:

            content_type = ContentType.objects.get_for_model(obj)
            target = f"{content_type.app_label}.{content_type.model}:{obj.pk}"

            if obj_repr:

                extra["object"] = obj_repr

        extra["admin_action"] = action

        AuditLog.objects.create(
            actor=user,
            action=f"admin.{action}",
            target=target[:200],
            ip=None,
            user_agent="",
            extra=extra
        )

    # Do nothing to prevent request interruption
    except Exception:

        pass
