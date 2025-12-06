from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.contrib.auth import get_user_model
from products.models import Product, Category, Brand
from .serializers import (
    UserSyncSerializer,
    ProductSyncSerializer,
    CategorySyncSerializer,
    BrandSyncSerializer,
)

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
        categories = Category.objects.filter(is_active=True)
        brands = Brand.objects.filter(is_active=True)
        products = Product.objects.filter(is_active=True)

        return Response(
            {
                "users": UserSyncSerializer(users, many=True).data,
                "categories": CategorySyncSerializer(categories, many=True).data,
                "brands": BrandSyncSerializer(brands, many=True).data,
                "products": ProductSyncSerializer(products, many=True).data,
                "sync_timestamp": timezone.now().isoformat(),
            }
        )

    @action(detail=False, methods=["get"])
    def pull_updates(self, request):
        try:
            since = request.query_params.get("since")
            store_id = request.query_params.get("store_id")

            if not since:
                return Response({"error": "since parameter required"}, status=400)

            users = User.objects.filter(updated_at__gte=since, is_active=True)
            categories = Category.objects.filter(updated_at__gte=since, is_active=True)
            brands = Brand.objects.filter(is_active=True)
            products = Product.objects.filter(updated_at__gte=since, is_active=True)

            has_updates = users.exists() or categories.exists() or products.exists()

            return Response(
                {
                    "users": UserSyncSerializer(users, many=True).data,
                    "categories": CategorySyncSerializer(categories, many=True).data,
                    "brands": BrandSyncSerializer(brands, many=True).data,
                    "products": ProductSyncSerializer(products, many=True).data,
                    "sync_timestamp": timezone.now().isoformat(),
                    "has_updates": has_updates,
                }
            )
        except Exception as e:
            import traceback

            error_detail = traceback.format_exc()
            print(f"Pull updates error: {error_detail}")
            return Response({"error": str(e), "traceback": error_detail}, status=500)
