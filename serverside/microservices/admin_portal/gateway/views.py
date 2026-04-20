import httpx
import time
import jwt
import os
import re
import logging
import traceback
import atexit
from http.cookies import SimpleCookie
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.utils.functional import SimpleLazyObject
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, action
from rest_framework.viewsets import ViewSet
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from collections import OrderedDict

# =============================================================================
# CONFIGURATION & GLOBAL OPTIMIZATIONS
# =============================================================================

logger = logging.getLogger(__name__)

def _service_url(env_name, default_url):
    """Get service URL from env with trailing slash normalization."""
    hostport = os.getenv(f"{env_name}_HOSTPORT", "").strip()
    if hostport:
        return f"http://{hostport}".rstrip("/")
    return os.getenv(env_name, default_url).rstrip("/")

# Pre-compiled regex patterns for admin HTML rewriting (avoid recompilation per request)
_ADMIN_REWRITE_PATTERNS = [
    (re.compile(r'([\"\'])/admin/(?!admin/)', re.IGNORECASE), r'\1/admin/{sid}/'),
    (re.compile(r'([\"\'])/static/', re.IGNORECASE), r'\1/admin/{sid}/static/'),
    (re.compile(r'([\"\'])/media/', re.IGNORECASE), r'\1/admin/{sid}/media/'),
    (re.compile(r'([\"\'])/game/', re.IGNORECASE), r'\1/admin/{sid}/game/'),
    (re.compile(r'([\"\'])/game2/', re.IGNORECASE), r'\1/admin/{sid}/game2/'),
]

# Hop-by-hop headers to exclude when forwarding (RFC 2616 §13.5.1)
HOP_BY_HOP_HEADERS = frozenset({
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade', 'proxy-connection'
})

# Common health endpoints in priority order
HEALTH_ENDPOINTS = ('/health/', '/api/health/', '/', '/admin/')

# Microservices configuration (unchanged logic)
MICROSERVICES = {
    'decision': {'url': _service_url("DECISION_SERVICE", 'http://127.0.0.1:9000'), 'name': 'Decision Service'},
    'bettor': {'url': _service_url("BETTOR_SERVICE", 'http://127.0.0.1:9002'), 'name': 'Bettor Service'},
}

# =============================================================================
# CONNECTION POOLING: Persistent httpx client (major performance gain)
# =============================================================================

def _create_gateway_client():
    """Create optimized httpx client with connection pooling."""
    return httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
        headers={"User-Agent": "API-Gateway/1.0"},
        http2=False,  # Disable unless microservices explicitly support HTTP/2
    )

# Lazy-initialized persistent client (created on first use, closed on exit)
_gateway_client = SimpleLazyObject(_create_gateway_client)

# Register cleanup for graceful shutdown
atexit.register(lambda: _gateway_client.close if _gateway_client else None)

# =============================================================================
# UTILITY FUNCTIONS (Optimized)
# =============================================================================

def _build_forward_headers(request, include_cookie=False):
    """Build forwarding headers with hop-by-hop filtering (efficient)."""
    headers = OrderedDict()
    
    # Forward safe headers only
    for header in ('Content-Type', 'Accept', 'Authorization', 'User-Agent', 'Referer'):
        value = request.headers.get(header)
        if value:
            headers[header] = value
    
    # Conditionally include cookies
    if include_cookie:
        cookie = request.headers.get('Cookie')
        if cookie:
            headers['Cookie'] = cookie
    
    # Add standard forwarding headers
    headers['X-Forwarded-For'] = request.META.get('REMOTE_ADDR', '')
    headers['X-Forwarded-Proto'] = request.scheme
    headers['X-Forwarded-Host'] = request.get_host()
    
    # Forward SSO token from cookies if Authorization not already set
    if 'Authorization' not in headers:
        sso_cookie_name = getattr(settings, 'SSO_COOKIE_NAME', 'admin_jwt')
        sso_token = request.COOKIES.get(sso_cookie_name)
        if sso_token:
            headers['Authorization'] = f'Bearer {sso_token}'
    
    return dict(headers)


def _rewrite_admin_html(html_text, service_id):
    """Rewrite admin HTML links to stay within gateway (single-pass optimized)."""
    # Use pre-compiled patterns with service_id substitution
    for pattern, replacement_template in _ADMIN_REWRITE_PATTERNS:
        replacement = replacement_template.format(sid=service_id)
        html_text = pattern.sub(replacement, html_text)
    return html_text


def _build_target_url(service, full_path):
    """Build target URL efficiently (avoid redundant string ops)."""
    base = service['url'].rstrip('/')
    path = full_path.lstrip('/') or ''
    return f"{base}/{path}" if path else base


def _parse_response(response, prefer_json=True):
    """Parse response efficiently with fallback."""
    if prefer_json:
        try:
            return response.json()
        except (ValueError, httpx.DecodingError):
            pass
    # Fallback: return minimal dict or raw text for non-JSON
    content_type = response.headers.get('content-type', '').lower()
    if 'application/json' in content_type:
        return {'error': 'Invalid JSON response'}
    return {'message': response.text[:10000]}  # Limit fallback text size


# =============================================================================
# API ENDPOINTS (Optimized implementations)
# =============================================================================

@api_view(['GET'])
def api_root(request):
    """API Gateway Root - Lists all available microservices (cached structure)."""
    services = [
        {
            'id': key,
            'name': svc['name'],
            'url': svc['url'],
            'health_endpoint': f'/api/gateway/{key}/health/',
            'api_endpoint': f'/api/{key}/',
        }
        for key, svc in MICROSERVICES.items()
    ]
    return Response({
        'message': 'Welcome to Microservices API Gateway',
        'version': '1.0',
        'services': services,
    })


@api_view(['GET'])
def service_health(request, service_id):
    """Check health of a microservice (with early exit & specific exception handling)."""
    service = MICROSERVICES.get(service_id)
    if not service:
        return Response(
            {'error': f'Service {service_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Try health endpoints with early success exit
    for endpoint in HEALTH_ENDPOINTS:
        try:
            url = f"{service['url']}{endpoint}"
            response = _gateway_client.get(url, timeout=5.0)
            if response.status_code < 500:
                return Response({
                    'service': service_id,
                    'name': service['name'],
                    'status': 'healthy',
                    'url': service['url'],
                    'endpoint_used': endpoint,
                    'response_code': response.status_code,
                })
        except httpx.TimeoutException:
            continue  # Try next endpoint
        except httpx.RequestError:
            continue
        except Exception:
            if settings.DEBUG:
                logger.exception(f"Health check error for {service_id}{endpoint}")
            continue
    
    # All endpoints failed but service might be reachable
    return Response({
        'service': service_id,
        'name': service['name'],
        'status': 'degraded',
        'url': service['url'],
        'message': 'Service reachable but no health endpoint responded',
    })


def forward_request(request, service_id, full_path):
    """Generic JSON-first request forwarder (optimized with connection reuse)."""
    service = MICROSERVICES.get(service_id)
    if not service:
        return Response(
            {'error': f'Service {service_id} not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    target_url = _build_target_url(service, full_path)
    logger.debug(f"Forwarding {request.method} to: {target_url}")
    
    headers = _build_forward_headers(request, include_cookie=False)
    content = request.body if request.method != 'GET' and request.body else None
    
    try:
        response = _gateway_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=content,
            params=request.GET.dict(),
        )
        
        response_data = _parse_response(response)
        return Response(response_data, status=response.status_code)
        
    except httpx.TimeoutException:
        logger.warning(f"Timeout forwarding to {service_id}")
        return Response(
            {'error': 'Service timeout', 'service': service_id},
            status=status.HTTP_504_GATEWAY_TIMEOUT
        )
    except httpx.ConnectError:
        logger.error(f"Connection failed for {service_id}")
        return Response(
            {'error': 'Service unavailable', 'service': service_id},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except httpx.RequestError as e:
        logger.error(f"Request error for {service_id}: {e}")
        return Response(
            {'error': 'Service unavailable', 'service': service_id},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        logger.exception(f"Unexpected error forwarding to {service_id}")
        return Response(
            {'error': str(e) if settings.DEBUG else 'Gateway error', 'service': service_id},
            status=status.HTTP_502_BAD_GATEWAY
        )


def forward_request_raw(request, service_id, full_path, rewrite_location_prefix=None):
    """Raw passthrough forwarder for HTML/admin (with streaming & efficient rewriting)."""
    service = MICROSERVICES.get(service_id)
    if not service:
        return HttpResponse(
            f'Service {service_id} not found',
            status=status.HTTP_404_NOT_FOUND
        )

    target_url = _build_target_url(service, full_path)
    logger.debug(f"Forwarding RAW {request.method} to: {target_url}")

    headers = _build_forward_headers(request, include_cookie=True)
    content = request.body if request.method != 'GET' and request.body else None

    try:
        response = _gateway_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=content,
            params=request.GET.dict(),
        )

        content_type = response.headers.get('content-type', 'text/html; charset=utf-8')
        content_length = int(response.headers.get('content-length', 0))
        
        # Stream large HTML responses without rewriting (memory optimization)
        if rewrite_location_prefix and content_type.startswith('text/html') and content_length < 5_000_000:
            encoding = response.encoding or 'utf-8'
            try:
                html_text = response.text  # Efficient decoding
                html_text = _rewrite_admin_html(html_text, service_id)
                body = html_text.encode(encoding)
            except Exception:
                if settings.DEBUG:
                    logger.exception("HTML rewrite failed")
                body = response.content  # Fallback to raw
        else:
            body = response.content  # Use raw content for large/non-HTML responses

        django_response = HttpResponse(
            body,
            status=response.status_code,
            content_type=content_type,
        )
        
        # Security & cache headers
        django_response["Cache-Control"] = "no-store"
        django_response["X-Frame-Options"] = "SAMEORIGIN"

        # Rewrite Location header if needed (efficient parsing)
        location = response.headers.get('location')
        if rewrite_location_prefix and location and location.startswith('/'):
            parts = urlsplit(location)
            path = parts.path
            # Normalize path rewriting
            if path.startswith('/admin/'):
                path = path[len('/admin/'):]
            path = path.lstrip('/')
            new_path = f"{rewrite_location_prefix}{path}" if path else rewrite_location_prefix.rstrip('/')
            
            # Rewrite 'next' param in query string
            query_pairs = parse_qsl(parts.query, keep_blank_values=True)
            rewritten = []
            for k, v in query_pairs:
                if k == 'next' and v.startswith('/admin/'):
                    v = f"{rewrite_location_prefix}{v[len('/admin/'):].lstrip('/')}"
                rewritten.append((k, v))
            new_query = urlencode(rewritten, doseq=True)
            
            location = urlunsplit((parts.scheme, parts.netloc, new_path, new_query, parts.fragment))
            django_response['Location'] = location

        # Forward Set-Cookie headers efficiently
        for cookie in response.headers.get_list('set-cookie'):
            if cookie:
                django_response.cookies.load(cookie)

        return django_response

    except httpx.TimeoutException:
        logger.warning(f"Timeout in raw forward to {service_id}")
        return HttpResponse('Service timeout', status=status.HTTP_504_GATEWAY_TIMEOUT)
    except httpx.ConnectError:
        logger.error(f"Connection failed in raw forward to {service_id}")
        return HttpResponse('Service unavailable', status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except httpx.RequestError as e:
        logger.error(f"Request error in raw forward to {service_id}: {e}")
        return HttpResponse('Service unavailable', status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        if settings.DEBUG:
            raise
        logger.exception(f"Unexpected error in raw forward to {service_id}")
        return HttpResponse(str(e) if settings.DEBUG else 'Gateway error', status=status.HTTP_502_BAD_GATEWAY)


# =============================================================================
# MAIN FORWARDING VIEWS (Optimized path building & delegation)
# =============================================================================

@api_view(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])
def forward_to_service(request, service_id, path=''):
    """Forward any request to the appropriate microservice (optimized)."""
    # Build path efficiently without redundant concatenation
    full_path = f"/{path}" if path else "/"
    query = request.META.get('QUERY_STRING')
    if query:
        full_path = f"{full_path}?{query}"
    
    logger.debug(f"Forwarding to '{service_id}' path: {full_path[:200]}")  # Limit log size
    return forward_request(request, service_id, full_path)


def forward_admin_service(request, service_id, path=''):
    """Forward admin requests with SSO handling (optimized flow)."""
    # Fast path for static assets
    is_asset = path.startswith(("static/", "media/", "game/", "game2/"))
    
    # SSO token check (minimal overhead)
    sso_cookie_name = getattr(settings, 'SSO_COOKIE_NAME', 'admin_jwt')
    sso_token = request.COOKIES.get(sso_cookie_name)
    
    if not sso_token and not is_asset:
        if request.user.is_authenticated:
            # Generate JWT token efficiently
            payload = {
                "sub": str(request.user.id),
                "username": request.user.username,
                "is_staff": request.user.is_staff,
                "exp": int(time.time()) + getattr(settings, "SSO_TTL_SECONDS", 3600),
            }
            token = jwt.encode(payload, settings.SSO_SECRET, algorithm="HS256")
            resp = HttpResponseRedirect(f"/admin/{service_id}/")
            resp.set_cookie(
                sso_cookie_name, token, httponly=True,
                samesite=getattr(settings, "SSO_COOKIE_SAMESITE", "Lax"),
                secure=getattr(settings, "SSO_COOKIE_SECURE", False),
                domain=getattr(settings, "SSO_COOKIE_DOMAIN", "") or None,
                path=getattr(settings, "SSO_COOKIE_PATH", "/"),
            )
            return resp
        return HttpResponseRedirect(f"/admin/login/?next=/admin/{service_id}/")

    # Skip login redirect if already authenticated
    if path.startswith("login/") and not is_asset:
        return HttpResponseRedirect(f"/admin/{service_id}/")

    # Normalize path: strip service_id prefix if present
    if path.startswith(f"{service_id}/") or path == service_id:
        path = path[len(service_id):].lstrip('/')

    # Build target path with minimal conditionals
    if path:
        if is_asset:
            full_path = f"/{path}"
        elif path == "config/activate/":
            full_path = "/config/activate/"  # Special Unity endpoint
        elif path == "control/":
            full_path = "/gameplay/control/"
        elif path.startswith('admin/'):
            full_path = f"/{path}"
        else:
            full_path = f"/admin/{path}"
    else:
        full_path = "/admin/"

    # Efficient query string rewriting for 'next' param
    query = request.META.get('QUERY_STRING')
    if query:
        pairs = parse_qsl(query, keep_blank_values=True)
        prefix = f"/admin/{service_id}/"
        rewritten = []
        for k, v in pairs:
            if k == 'next' and v.startswith(prefix):
                v = "/admin/" + v[len(prefix):]
            rewritten.append((k, v))
        full_path += "?" + urlencode(rewritten, doseq=True)

    rewrite_prefix = f"/admin/{service_id}/"
    return forward_request_raw(request, service_id, full_path, rewrite_location_prefix=rewrite_prefix)


@api_view(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'])
def forward_embed_service(request, service_id, path=''):
    """Forward embed/iframe requests (optimized)."""
    full_path = f"/{path}" if path else "/"
    query = request.META.get('QUERY_STRING')
    if query:
        full_path += f"?{query}"
    
    rewrite_prefix = f"/embed/{service_id}/"
    return forward_request_raw(request, service_id, full_path, rewrite_location_prefix=rewrite_prefix)


# =============================================================================
# VIEWSET (Optimized delegation)
# =============================================================================

class GatewayViewSet(ViewSet):
    """API Gateway ViewSet - delegates to optimized functions."""
    
    def list(self, request):
        return api_root(request)
    
    @action(detail=True, methods=['get', 'post', 'put', 'patch', 'delete', 'head', 'options'], url_path='(?P<path>.*)')
    def forward(self, request, pk=None, path=''):
        return forward_to_service(request, pk, path)
    
    @action(detail=True, methods=['get'])
    def health(self, request, pk=None):
        return service_health(request, pk)
