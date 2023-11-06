"""circle_service URL Configuration
"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from circle_service.router_urls import router_urlpatterns, router_admin_urlpatterns

urlpatterns = [
    path("api/circles/", include(router_urlpatterns)),
    path("api/admin/circles/", include(router_admin_urlpatterns)),
    path("api/circles/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Optional UI:
    path(
        "api/circles/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/circles/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
