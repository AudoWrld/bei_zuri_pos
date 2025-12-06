from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from products.models import Product, Category, Brand
from sales.models import Sale, SaleItem, Return, ReturnItem
from .serializers import (
    UserSyncSerializer,
    ProductSyncSerializer,
    CategorySyncSerializer,
    BrandSyncSerializer,
    SaleSyncSerializer,
    ReturnSyncSerializer,
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

    @action(detail=False, methods=["post"])
    def push_sales(self, request):
        try:
            store_id = request.data.get("store_id")
            sales_data = request.data.get("sales", [])

            if not sales_data:
                return Response({"success": True, "message": "No sales to sync"})

            synced_count = 0
            error_count = 0

            with transaction.atomic():
                for sale_data in sales_data:
                    try:
                        cashier = User.objects.filter(
                            id=sale_data["cashier_id"]
                        ).first()

                        if not cashier:
                            print(f"Cashier not found: {sale_data['cashier_id']}")
                            error_count += 1
                            continue

                        sale, created = Sale.objects.update_or_create(
                            sale_number=sale_data["sale_number"],
                            defaults={
                                "sale_type": sale_data["sale_type"],
                                "cashier": cashier,
                                "total_amount": sale_data["total_amount"],
                                "discount_amount": sale_data["discount_amount"],
                                "final_amount": sale_data["final_amount"],
                                "payment_method": sale_data["payment_method"],
                                "money_received": sale_data.get("money_received"),
                                "change_amount": sale_data.get("change_amount"),
                                "notes": sale_data.get("notes", ""),
                                "created_at": sale_data["created_at"],
                                "completed_at": sale_data["completed_at"],
                            },
                        )

                        for item_data in sale_data.get("items", []):
                            product = Product.objects.filter(
                                id=item_data["product_id"]
                            ).first()

                            if not product:
                                print(f"Product not found: {item_data['product_id']}")
                                continue

                            SaleItem.objects.update_or_create(
                                sale=sale,
                                product=product,
                                defaults={
                                    "quantity": item_data["quantity"],
                                    "unit_price": item_data["unit_price"],
                                    "discount_amount": item_data["discount_amount"],
                                    "total_amount": item_data["total_amount"],
                                },
                            )

                        synced_count += 1

                    except Exception as e:
                        error_count += 1
                        print(f"Error syncing sale {sale_data.get('sale_number')}: {e}")
                        import traceback

                        traceback.print_exc()

            return Response(
                {
                    "success": True,
                    "synced_count": synced_count,
                    "error_count": error_count,
                    "message": f"Synced {synced_count} sales, {error_count} errors",
                }
            )

        except Exception as e:
            import traceback

            error_detail = traceback.format_exc()
            print(f"Push sales error: {error_detail}")
            return Response(
                {"success": False, "error": str(e), "traceback": error_detail},
                status=500,
            )

    @action(detail=False, methods=["post"])
    def push_returns(self, request):
        try:
            store_id = request.data.get("store_id")
            returns_data = request.data.get("returns", [])

            if not returns_data:
                return Response({"success": True, "message": "No returns to sync"})

            synced_count = 0
            error_count = 0

            with transaction.atomic():
                for return_data in returns_data:
                    try:
                        cashier = User.objects.filter(
                            id=return_data["cashier_id"]
                        ).first()

                        if not cashier:
                            print(f"Cashier not found: {return_data['cashier_id']}")
                            error_count += 1
                            continue

                        sale = Sale.objects.filter(
                            sale_number=return_data["sale_number"]
                        ).first()

                        if not sale:
                            print(f"Sale not found: {return_data['sale_number']}")
                            error_count += 1
                            continue

                        return_obj, created = Return.objects.update_or_create(
                            return_number=return_data["return_number"],
                            defaults={
                                "sale": sale,
                                "cashier": cashier,
                                "total_return_amount": return_data[
                                    "total_return_amount"
                                ],
                                "notes": return_data.get("notes", ""),
                                "created_at": return_data["created_at"],
                            },
                        )

                        for item_data in return_data.get("items", []):
                            sale_item = SaleItem.objects.filter(
                                id=item_data["sale_item_id"]
                            ).first()

                            if not sale_item:
                                print(
                                    f"Sale item not found: {item_data['sale_item_id']}"
                                )
                                continue

                            ReturnItem.objects.update_or_create(
                                return_fk=return_obj,
                                sale_item=sale_item,
                                defaults={
                                    "quantity": item_data["quantity"],
                                    "return_reason": item_data["return_reason"],
                                    "unit_price": item_data["unit_price"],
                                    "total_price": item_data["total_price"],
                                },
                            )

                        synced_count += 1

                    except Exception as e:
                        error_count += 1
                        print(
                            f"Error syncing return {return_data.get('return_number')}: {e}"
                        )
                        import traceback

                        traceback.print_exc()

            return Response(
                {
                    "success": True,
                    "synced_count": synced_count,
                    "error_count": error_count,
                    "message": f"Synced {synced_count} returns, {error_count} errors",
                }
            )

        except Exception as e:
            import traceback

            error_detail = traceback.format_exc()
            print(f"Push returns error: {error_detail}")
            return Response(
                {"success": False, "error": str(e), "traceback": error_detail},
                status=500,
            )
