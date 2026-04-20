import time
import logging
import jwt
from functools import lru_cache
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.core.exceptions import SuspiciousOperation

from gateway import views as gateway_views

logger = logging.getLogger(__name__)

# =============================================================================
# CACHED SETTINGS ACCESSORS (Efficient, thread-safe)
# =============================================================================

@lru_cache(maxsize=1)
def _get_sso_cookie_attrs():
    """Cached cookie attributes for consistent, efficient reuse."""
    return {
        'httponly': True,
        'samesite': getattr(settings, 'SSO_COOKIE_SAMESITE', 'Lax'),
        'secure': getattr(settings, 'SSO_COOKIE_SECURE', False),
        'domain': getattr(settings, 'SSO_COOKIE_DOMAIN', '') or None,
        'path': getattr(settings, 'SSO_COOKIE_PATH', '/'),
    }

@lru_cache(maxsize=1)
def _get_sso_secret():
    """Cached SSO secret key access."""
    return getattr(settings, 'SSO_SECRET', '')

@lru_cache(maxsize=1)
def _get_sso_ttl_seconds():
    """Cached SSO TTL access."""
    return getattr(settings, 'SSO_TTL_SECONDS', 3600)

@lru_cache(maxsize=1)
def _get_sso_cookie_name():
    """Cached SSO cookie name access."""
    return getattr(settings, 'SSO_COOKIE_NAME', 'admin_jwt')


# =============================================================================
# JWT HELPER (Centralized, safe, reusable)
# =============================================================================

def _create_sso_token(user):
    """
    Create SSO JWT token for authenticated user.
    Returns token string or None on error.
    """
    try:
        payload = {
            'sub': str(user.id),
            'username': user.username,
            'is_staff': getattr(user, 'is_staff', False),
            'exp': int(time.time()) + _get_sso_ttl_seconds(),
        }
        return jwt.encode(payload, _get_sso_secret(), algorithm='HS256')
    except Exception as e:
        logger.error(f"Failed to create SSO token for user {user.id}: {e}")
        return None


# =============================================================================
# VIEW: admin_home (Optimized)
# =============================================================================

@login_required
@require_http_methods(['GET'])
def admin_home(request):
    """
    Render admin portal home page.
    Optimized: Minimal overhead, method restriction.
    """
    # Admin context is lightweight; render directly
    return render(request, 'portal/home.html', admin.site.each_context(request))


# =============================================================================
# VIEW: analytics_embed (Optimized)
# =============================================================================

@login_required
@require_http_methods(['GET'])
def analytics_embed(request):
    """
    Render analytics embed page with validated range parameter.
    Optimized: Input validation, efficient context merging.
    """
    # Validate and sanitize range parameter
    range_value = request.GET.get('range', '30')
    try:
        # Accept only positive integers within reasonable bounds
        range_int = int(range_value)
        if not (1 <= range_int <= 365):
            raise ValueError
    except (ValueError, TypeError):
        logger.warning(f"Invalid analytics range parameter: {range_value}")
        return HttpResponseBadRequest('Invalid range parameter. Use 1-365.')
    
    # Build context efficiently: admin context first, then override with range
    context = admin.site.each_context(request)
    context['range'] = str(range_int)  # Ensure string for template safety
    
    return render(request, 'portal/analytics_embed.html', context)


# =============================================================================
# VIEW: issue_token (Optimized)
# =============================================================================

@login_required
@require_http_methods(['POST'])  # Token issuance should be POST for CSRF protection
def issue_token(request):
    """
    Issue SSO JWT token and set secure cookie.
    Optimized: Cached settings, centralized token creation, error handling.
    """
    token = _create_sso_token(request.user)
    
    if not token:
        logger.error(f"Token creation failed for user {request.user.id}")
        return JsonResponse(
            {'error': 'Token generation failed'},
            status=500
        )
    
    # Build response with token
    response = JsonResponse({'token': token})
    
    # Set cookie using cached attributes (efficient, consistent)
    response.set_cookie(
        _get_sso_cookie_name(),
        token,
        **_get_sso_cookie_attrs()
    )
    
    logger.debug(f"Issued SSO token for user {request.user.username}")
    return response


# =============================================================================
# VIEW: unity_game2_proxy (Compatibility)
# =============================================================================

@login_required
@require_http_methods(["GET", "HEAD"])
def unity_game2_proxy(request, path=""):
    """
    Compatibility route: serve Unity WebGL build from /game2/* on the admin portal origin.

    The actual build is hosted under the decision_service at /gameplay/game2/*.
    """
    safe_path = str(path or "").lstrip("/")
    full_path = f"/gameplay/game2/{safe_path}" if safe_path else "/gameplay/game2/"
    return gateway_views.forward_request_raw(request, "decision", full_path)
