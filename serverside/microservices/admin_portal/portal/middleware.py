import time
import logging
import jwt
from jwt import InvalidTokenError, ExpiredSignatureError, DecodeError
from functools import lru_cache
from django.conf import settings
from django.http import HttpResponseRedirect
from django.contrib.auth import login, get_user_model
from django.db import transaction

logger = logging.getLogger(__name__)
User = get_user_model()  # Safe user model reference (supports custom User models)

# =============================================================================
# SETTINGS VALIDATION & CACHED ACCESSORS (Fail fast, access efficiently)
# =============================================================================

def _validate_sso_settings():
    """Validate required SSO settings at import time to prevent runtime crashes."""
    required = ['SSO_SECRET', 'SSO_COOKIE_NAME', 'SSO_TTL_SECONDS', 'SSO_REFRESH_WINDOW_SECONDS']
    missing = [s for s in required if not hasattr(settings, s)]
    if missing:
        raise ImproperlyConfigured(f"SSO middleware requires settings: {', '.join(missing)}")

# Run validation once when module loads
try:
    from django.core.exceptions import ImproperlyConfigured
    _validate_sso_settings()
except ImportError:
    # Django not fully loaded yet (e.g., during manage.py check) - defer validation
    pass

@lru_cache(maxsize=1)
def _get_sso_cookie_name():
    """Cached access to SSO cookie name setting."""
    return getattr(settings, 'SSO_COOKIE_NAME', 'admin_jwt')

@lru_cache(maxsize=1)
def _get_sso_secret():
    """Cached access to SSO secret setting."""
    return getattr(settings, 'SSO_SECRET', '')

@lru_cache(maxsize=1)
def _get_sso_ttl_seconds():
    """Cached access to SSO TTL setting."""
    return getattr(settings, 'SSO_TTL_SECONDS', 3600)

@lru_cache(maxsize=1)
def _get_sso_refresh_window():
    """Cached access to SSO refresh window setting."""
    return getattr(settings, 'SSO_REFRESH_WINDOW_SECONDS', 300)

@lru_cache(maxsize=1)
def _get_sso_cookie_attrs():
    """Cached cookie attributes dict for efficient reuse."""
    return {
        'httponly': True,
        'samesite': getattr(settings, 'SSO_COOKIE_SAMESITE', 'Lax'),
        'secure': getattr(settings, 'SSO_COOKIE_SECURE', False),
        'domain': getattr(settings, 'SSO_COOKIE_DOMAIN', '') or None,
        'path': getattr(settings, 'SSO_COOKIE_PATH', '/'),
    }

@lru_cache(maxsize=1)
def _get_canonical_host():
    """Cached canonical host for redirect middleware."""
    return getattr(settings, 'SSO_CANONICAL_HOST', '')


# =============================================================================
# JWT HELPERS (Centralized, efficient, safe)
# =============================================================================

def _decode_sso_token(token, verify_exp=True):
    """Decode SSO JWT token with centralized error handling."""
    if not token:
        return None
    try:
        return jwt.decode(
            token,
            _get_sso_secret(),
            algorithms=['HS256'],
            options={'verify_exp': verify_exp}
        )
    except (ExpiredSignatureError, InvalidTokenError, DecodeError, ValueError) as e:
        logger.debug(f"SSO token decode failed: {type(e).__name__}")
        return None

def _encode_sso_token(user):
    """Encode SSO JWT token for authenticated user."""
    payload = {
        'sub': str(user.id),
        'username': user.username,
        'is_staff': user.is_staff,
        'exp': int(time.time()) + _get_sso_ttl_seconds(),
    }
    return jwt.encode(payload, _get_sso_secret(), algorithm='HS256')


# =============================================================================
# MIDDLEWARE: CanonicalHostMiddleware (Optimized)
# =============================================================================

class CanonicalHostMiddleware:
    """
    Redirects non-canonical host requests to the canonical host.
    Optimized: Cached settings access, early-exit logic.
    """
    
    sync_capable = True
    async_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        self._canonical_host = _get_canonical_host()  # Cache at init

    def __call__(self, request):
        # Early exit: no canonical host configured
        if not self._canonical_host:
            return self.get_response(request)
        
        # Early exit: already on canonical host
        current_host = request.get_host()
        if current_host == self._canonical_host:
            return self.get_response(request)
        
        # Redirect to canonical host preserving full path and query
        redirect_url = f"{request.scheme}://{self._canonical_host}{request.get_full_path()}"
        logger.info(f"Redirecting from {current_host} to canonical host: {self._canonical_host}")
        return HttpResponseRedirect(redirect_url)


# =============================================================================
# MIDDLEWARE: SSOLoginRedirectMiddleware (Optimized)
# =============================================================================

class SSOLoginRedirectMiddleware:
    """
    Auto-authenticates users via SSO JWT cookie and redirects logged-in users away from login pages.
    Optimized: Minimal DB hits, cached settings, deferred writes.
    """
    
    sync_capable = True
    async_capable = False

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip if user already authenticated (Django session)
        if getattr(request.user, 'is_authenticated', False):
            return self._handle_authenticated_redirect(request)
        
        # Attempt SSO cookie authentication
        self._attempt_sso_login(request)
        
        # Handle login page redirect for newly authenticated users
        return self._handle_authenticated_redirect(request)

    def _attempt_sso_login(self, request):
        """Attempt to authenticate user from SSO cookie (idempotent, safe)."""
        token = request.COOKIES.get(_get_sso_cookie_name())
        if not token:
            return
        
        payload = _decode_sso_token(token, verify_exp=True)
        if not payload:
            return
        
        try:
            username = payload.get('username') or f"user-{payload.get('sub')}"
            
            # Efficient get_or_create with minimal DB hit
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'is_staff': True, 'is_superuser': True}
            )
            
            # Only update if user exists AND lacks required permissions
            if not created and (not user.is_staff or not user.is_superuser):
                user.is_staff = True
                user.is_superuser = True
                # Use update_fields to minimize DB write scope
                user.save(update_fields=['is_staff', 'is_superuser'])
                logger.info(f"Updated permissions for SSO user: {username}")
            
            # Authenticate and attach user to request
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            logger.debug(f"SSO login successful for user: {username}")
            
        except Exception as e:
            # Log but don't crash - fail open to allow normal auth flow
            logger.warning(f"SSO login failed for token: {type(e).__name__}")

    def _handle_authenticated_redirect(self, request):
        """Redirect authenticated users away from login pages."""
        if request.path.startswith('/admin/login/') and request.user.is_authenticated:
            logger.debug(f"Redirecting authenticated user away from login: {request.path}")
            return HttpResponseRedirect('/admin/')
        return self.get_response(request)


# =============================================================================
# MIDDLEWARE: SSOAutoRefreshMiddleware (Optimized)
# =============================================================================

class SSOAutoRefreshMiddleware:
    """
    Auto-refreshes SSO JWT cookie before expiration.
    Optimized: Single token decode per request, conditional cookie writes.
    """
    
    sync_capable = True
    async_capable = False

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request first to get response object
        response = self.get_response(request)
        
        # Skip if user not authenticated or no SSO cookie present
        if not getattr(request.user, 'is_authenticated', False):
            return response
        
        cookie_name = _get_sso_cookie_name()
        current_token = request.COOKIES.get(cookie_name)
        
        # Determine if token needs refresh
        if self._needs_token_refresh(current_token):
            new_token = _encode_sso_token(request.user)
            response.set_cookie(cookie_name, new_token, **_get_sso_cookie_attrs())
            logger.debug(f"Refreshed SSO token for user: {request.user.username}")
        
        return response

    def _needs_token_refresh(self, token):
        """
        Determine if token needs refresh based on expiration window.
        Returns True if token is missing, invalid, or expiring soon.
        """
        if not token:
            return True
        
        payload = _decode_sso_token(token, verify_exp=False)
        if not payload:
            return True
        
        try:
            exp = int(payload.get('exp') or 0)
            now = int(time.time())
            refresh_window = _get_sso_refresh_window()
            
            # Refresh if token expires within the refresh window
            return (exp - now) <= refresh_window
        except (ValueError, TypeError):
            # Malformed exp claim - refresh to be safe
            return True