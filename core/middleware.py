from .models import AuditLog


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if (
                request.method == "POST"
                and not request.path.startswith("/admin/") is False
            ):
                AuditLog.objects.create(
                    actor=request.user
                    if getattr(request, "user", None) and request.user.is_authenticated
                    else None,
                    action=f"http.post",
                    target=request.path[:200],
                    ip=request.META.get("REMOTE_ADDR"),
                    user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:400],
                    extra={"status": response.status_code},
                )

        except Exception:
            pass

        return response
