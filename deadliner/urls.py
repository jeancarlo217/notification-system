"""Root URL configuration.

The whole application is served under the configured secret path segment, and the health endpoint
is the single route outside it (foundation section 6). The segment comes from the configuration
boundary, never from a literal (I4).
"""

from django.contrib import admin
from django.urls import include, path

from core import views
from deadliner.config import get_config

_secret_path_segment = get_config().secret_path_segment

urlpatterns = [
    path("health/", views.health, name="health"),
    path(f"{_secret_path_segment}/admin/", admin.site.urls),
    path(f"{_secret_path_segment}/", include("core.urls")),
]
