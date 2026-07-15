import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Admin path loaded from environment so the URL is not publicly guessable.
# Set DJANGO_ADMIN_URL in production (e.g. "secure-panel-7x4k/").
# Falls back to "admin/" in development only.
_admin_path = os.environ.get('DJANGO_ADMIN_URL', 'admin/' if settings.DEBUG else None)
if not _admin_path:
    raise RuntimeError(
        "DJANGO_ADMIN_URL environment variable must be set in production. "
        "Example: DJANGO_ADMIN_URL=secure-panel-a1b2c3/"
    )

urlpatterns = [
    path(_admin_path, admin.site.urls),
    path('', include('userauths.urls')),
    path('', include('school.urls')),
    path('', include('kiswate_digital_app.urls')),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
