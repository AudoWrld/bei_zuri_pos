from django.urls import path
from .views import SyncAPIViewSet

urlpatterns = [
    path(
        "api/sync/health/",
        SyncAPIViewSet.as_view({"get": "health"}),
        name="sync-health",
    ),
    path(
        "api/sync/initial_sync/",
        SyncAPIViewSet.as_view({"post": "initial_sync"}),
        name="sync-initial",
    ),
    path(
        "api/sync/pull_updates/",
        SyncAPIViewSet.as_view({"get": "pull_updates"}),
        name="sync-pull",
    ),
    path(
        "api/sync/push_sales/",
        SyncAPIViewSet.as_view({"post": "push_sales"}),
        name="sync-push-sales",
    ),
    path(
        "api/sync/push_returns/",
        SyncAPIViewSet.as_view({"post": "push_returns"}),
        name="sync-push-returns",
    ),
]
