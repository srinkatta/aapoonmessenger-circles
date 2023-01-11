"""circle_service URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from circle_service.router_urls import router_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/circles/", include(router_urlpatterns)),
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
