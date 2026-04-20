import jwt
import re
from jwt import InvalidTokenError
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User

class AdminSSOMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return self.get_response(request)

        auth = request.META.get("HTTP_AUTHORIZATION", "")
        token = ""
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
        if not token:
            cookie_name = getattr(settings, "SSO_COOKIE_NAME", "admin_jwt")
            token = request.COOKIES.get(cookie_name, "")
        if settings.DEBUG:
            print(
                f"[SSO@decision] path={request.path} "
                f"auth_header={'yes' if auth else 'no'} "
                f"token_present={'yes' if token else 'no'}"
            )
        if token:
            try:
                payload = jwt.decode(token, settings.SSO_SECRET, algorithms=["HS256"])
            except InvalidTokenError as e:
                if settings.DEBUG:
                    print(f"[SSO@decision] token decode failed: {e}")
                return self.get_response(request)

            if payload.get("is_staff"):
                username = payload.get("username") or f"user-{payload.get('sub')}"
                user, created = User.objects.get_or_create(username=username)
                if created:
                    user.is_staff = True
                    user.is_superuser = True
                    user.save()
                else:
                    if not user.is_staff or not user.is_superuser:
                        user.is_staff = True
                        user.is_superuser = True
                        user.save(update_fields=["is_staff", "is_superuser"])
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return self.get_response(request)


class SafeHostMiddleware:
    _valid_host_pattern = re.compile(r"^[A-Za-z0-9.-]+(?::\d+)?$")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.META.get("HTTP_HOST", "")
        forwarded_host = request.META.get("HTTP_X_FORWARDED_HOST", "")

        if host and not self._valid_host_pattern.fullmatch(host):
            replacement = forwarded_host or self._default_host(request)
            request.META["HTTP_HOST"] = replacement
            request.META["SERVER_NAME"] = replacement.split(":", 1)[0]
            if ":" in replacement:
                request.META["SERVER_PORT"] = replacement.split(":", 1)[1]

        return self.get_response(request)

    @staticmethod
    def _default_host(request):
        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", None) or []
        candidate = next(
            (
                item
                for item in allowed_hosts
                if item not in {"*", ""}
                and "*" not in item
                and not item.startswith(".")
            ),
            "127.0.0.1",
        )
        port = request.META.get("SERVER_PORT")
        return f"{candidate}:{port}" if port else candidate
