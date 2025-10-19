from .models import AuditLog

class AuditMiddleware:

    def __init__(self, get_response):

        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        try:

            # Log all POSTs except for admins
            if request.method == "POST" and not request.path.startswith("/admin/"):

                # Get the actor
                actor = None

                if hasattr(request, "user") and request.user.is_authenticated:

                    actor = request.user

                # Get user agent and truncate it if needed
                user_agent = request.META.get("HTTP_USER_AGENT", "")[:400]

                AuditLog.objects.create(
                    actor=actor,
                    action="http.post",
                    target=request.path[:200],
                    ip=request.META.get("REMOTE_ADDR"),
                    user_agent=user_agent,
                    extra={"status": response.status_code},
                )

        # Do nothing to not interrupt requests
        except Exception:

            pass

        return response
