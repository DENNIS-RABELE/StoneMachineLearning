import jwt
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
        if token:
            try:
                payload = jwt.decode(token, settings.SSO_SECRET, algorithms=["HS256"])
            except InvalidTokenError:
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

