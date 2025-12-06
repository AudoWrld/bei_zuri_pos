from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.contrib.auth import get_user_model
from .serializers import UserSyncSerializer

User = get_user_model()


class SyncAPIViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def health(self, request):
        return Response({"status": "ok", "timestamp": timezone.now().isoformat()})

    @action(detail=False, methods=["post"])
    def initial_sync(self, request):
        store_id = request.data.get("store_id")

        users = User.objects.filter(is_active=True)

        return Response(
            {
                "users": UserSyncSerializer(users, many=True).data,
                "sync_timestamp": timezone.now().isoformat(),
            }
        )

    @action(detail=False, methods=["get"])
    def pull_updates(self, request):
        since = request.query_params.get("since")
        store_id = request.query_params.get("store_id")

        if not since:
            return Response({"error": "since parameter required"}, status=400)

        users = User.objects.filter(updated_at__gte=since, is_active=True)

        return Response(
            {
                "users": UserSyncSerializer(users, many=True).data,
                "sync_timestamp": timezone.now().isoformat(),
                "has_updates": users.exists(),
            }
        )
