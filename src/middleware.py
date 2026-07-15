class ContentSecurityPolicyMiddleware:
    """
    Adds a Content-Security-Policy header to every response.
    Tightened in production (DEBUG=False); permissive in dev to avoid breaking
    hot-reload / inline scripts in the admin / CDN assets.
    """

    # CDNs used by the project
    _CDN = " ".join([
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "https://fonts.googleapis.com",
        "https://fonts.gstatic.com",
        "https://unpkg.com",
    ])

    def __init__(self, get_response):
        self.get_response = get_response
        from django.conf import settings
        self.debug = getattr(settings, 'DEBUG', True)

    def __call__(self, request):
        response = self.get_response(request)
        if self.debug:
            # In dev, use Report-Only so the app never breaks but violations show in console
            response['Content-Security-Policy-Report-Only'] = self._build_policy(relaxed=True)
        else:
            response['Content-Security-Policy'] = self._build_policy(relaxed=False)
        return response

    def _build_policy(self, relaxed: bool) -> str:
        cdn = self._CDN
        # 'unsafe-inline' is needed for Bootstrap tooltips and some admin JS — tighten later
        # with a nonce-based approach when ready.
        script_src = f"'self' {cdn} 'unsafe-inline'" if relaxed else f"'self' {cdn}"
        style_src  = f"'self' {cdn} 'unsafe-inline'"   # Bootstrap requires unsafe-inline styles
        return "; ".join([
            f"default-src 'self'",
            f"script-src {script_src}",
            f"style-src {style_src}",
            f"img-src 'self' data: blob: https:",
            f"font-src 'self' {cdn}",
            f"connect-src 'self'",
            f"frame-ancestors 'none'",
            f"base-uri 'self'",
            f"form-action 'self'",
            f"object-src 'none'",
        ])
