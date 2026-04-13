import time
import logging
from collections import defaultdict
from django.http import HttpResponse
from django.conf import settings

app_logger = logging.getLogger('serpantsupply')
security_logger = logging.getLogger('serpantsupply.security')


class RateLimitMiddleware:
    """Simple in-memory rate limiter. Replace with Redis in production."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.requests = defaultdict(list)
        self.limit = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)
        self.window = getattr(settings, 'RATE_LIMIT_WINDOW', 60)

    def __call__(self, request):
        ip = self._get_client_ip(request)
        now = time.time()
        self.requests[ip] = [t for t in self.requests[ip] if now - t < self.window]

        if len(self.requests[ip]) >= self.limit:
            security_logger.warning(f'Rate limit exceeded for IP: {ip}')
            return HttpResponse(
                '<h1>429 Too Many Requests</h1><p>Slow down and try again.</p>',
                status=429, content_type='text/html'
            )

        self.requests[ip].append(now)
        return self.get_response(request)

    def _get_client_ip(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '0.0.0.0')


class RequestLoggingMiddleware:
    """Log every request with method, path, status, and duration."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        response = self.get_response(request)
        duration_ms = round((time.time() - start) * 1000, 1)
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '-'))
        user = request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'anon'
        app_logger.info(
            f'{request.method} {request.path} → {response.status_code} '
            f'[{duration_ms}ms] user={user} ip={ip}'
        )
        return response
