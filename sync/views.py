from rest_framework import viewsets, status
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
import traceback

User = get_user_model()


class SyncAPIViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def health(self, request):
        """Health check endpoint"""
        return Response({"status": "ok", "timestamp": timezone.now().isoformat()})

    @action(detail=False, methods=["get"])
    def pull_sales(self, request):
        """Send sales to POS terminals"""
        try:
            since = request.query_params.get("since")
            store_id = request.query_params.get("store_id")

            if not since:
                return Response({"error": "since parameter required"}, status=400)

            sales = (
                Sale.objects.filter(completed_at__gte=since, completed_at__isnull=False)
                .select_related("cashier")
                .prefetch_related("items__product")
            )

            sales_data = []
            for sale in sales:
                items_data = []
                for item in sale.items.all():
                    items_data.append(
                        {
                            "product_id": item.product.id,
                            "quantity": item.quantity,
                            "unit_price": str(item.unit_price),
                            "discount_amount": str(item.discount_amount),
                            "total_amount": str(item.total_amount),
                        }
                    )

                sales_data.append(
                    {
                        "sale_number": sale.sale_number,
                        "sale_type": sale.sale_type,
                        "cashier_id": sale.cashier.id,
                        "total_amount": str(sale.total_amount),
                        "discount_amount": str(sale.discount_amount),
                        "final_amount": str(sale.final_amount),
                        "payment_method": sale.payment_method,
                        "money_received": (
                            str(sale.money_received) if sale.money_received else None
                        ),
                        "change_amount": (
                            str(sale.change_amount) if sale.change_amount else None
                        ),
                        "notes": sale.notes,
                        "created_at": sale.created_at.isoformat(),
                        "completed_at": sale.completed_at.isoformat(),
                        "items": items_data,
                    }
                )

            return Response(
                {
                    "sales": sales_data,
                    "count": len(sales_data),
                    "sync_timestamp": timezone.now().isoformat(),
                }
            )

        except Exception as e:
            error_detail = traceback.format_exc()
            print(f"Pull sales error: {error_detail}")
            return Response({"error": str(e), "traceback": error_detail}, status=500)

    @action(detail=False, methods=["get"])
    def pull_returns(self, request):
        """Send returns to POS terminals"""
        try:
            since = request.query_params.get("since")
            store_id = request.query_params.get("store_id")

            if not since:
                return Response({"error": "since parameter required"}, status=400)

            returns = (
                Return.objects.filter(created_at__gte=since)
                .select_related("cashier", "sale")
                .prefetch_related("items__sale_item__product")
            )

            returns_data = []
            for return_obj in returns:
                items_data = []
                for item in return_obj.items.all():
                    items_data.append(
                        {
                            "product_id": item.sale_item.product.id,
                            "sale_item_id": item.sale_item.id,
                            "quantity": item.quantity,
                            "return_reason": item.return_reason,
                            "unit_price": str(item.unit_price),
                            "total_price": str(item.total_price),
                        }
                    )

                returns_data.append(
                    {
                        "return_number": return_obj.return_number,
                        "sale_number": return_obj.sale.sale_number,
                        "cashier_id": return_obj.cashier.id,
                        "total_return_amount": str(return_obj.total_return_amount),
                        "notes": return_obj.notes,
                        "created_at": return_obj.created_at.isoformat(),
                        "items": items_data,
                    }
                )

            return Response(
                {
                    "returns": returns_data,
                    "count": len(returns_data),
                    "sync_timestamp": timezone.now().isoformat(),
                }
            )

        except Exception as e:
            error_detail = traceback.format_exc()
            print(f"Pull returns error: {error_detail}")
            return Response({"error": str(e), "traceback": error_detail}, status=500)

    def initial_sync(self, request):
        """Initial sync - send all active data to POS"""
        try:
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
        except Exception as e:
            error_detail = traceback.format_exc()
            print(f"Initial sync error: {error_detail}")
            return Response({"error": str(e), "traceback": error_detail}, status=500)

    @action(detail=False, methods=["get"])
    def pull_updates(self, request):
        """Pull updates since last sync"""
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
            error_detail = traceback.format_exc()
            print(f"Pull updates error: {error_detail}")
            return Response({"error": str(e), "traceback": error_detail}, status=500)

    @action(detail=False, methods=["post"])
    def push_sales(self, request):
        """Receive sales from POS"""
        try:
            store_id = request.data.get("store_id")
            sales_data = request.data.get("sales", [])

            if not sales_data:
                return Response({"success": True, "message": "No sales to sync"})

            synced_count = 0
            error_count = 0
            errors = []

            with transaction.atomic():
                for sale_data in sales_data:
                    try:
                        cashier = User.objects.filter(
                            id=sale_data["cashier_id"]
                        ).first()

                        if not cashier:
                            error_msg = f"Cashier not found: {sale_data['cashier_id']}"
                            print(error_msg)
                            errors.append(
                                {
                                    "sale": sale_data.get("sale_number"),
                                    "error": error_msg,
                                }
                            )
                            error_count += 1
                            continue

                        sale, created = Sale.objects.update_or_create(
                            sale_number=sale_data["sale_number"],
                            defaults={
                                "sale_type": sale_data["sale_type"],
                                "cashier": cashier,
                                "total_amount": sale_data["total_amount"],
                                "discount_amount": sale_data.get("discount_amount", 0),
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
                                    "discount_amount": item_data.get(
                                        "discount_amount", 0
                                    ),
                                    "total_amount": item_data["total_amount"],
                                },
                            )

                        synced_count += 1
                        print(f"Synced sale: {sale_data['sale_number']}")

                    except Exception as e:
                        error_count += 1
                        error_msg = f"Error syncing sale {sale_data.get('sale_number')}: {str(e)}"
                        print(error_msg)
                        errors.append(
                            {"sale": sale_data.get("sale_number"), "error": str(e)}
                        )
                        traceback.print_exc()

            response_data = {
                "success": True,
                "synced_count": synced_count,
                "error_count": error_count,
                "message": f"Synced {synced_count} sales, {error_count} errors",
            }

            if errors:
                response_data["errors"] = errors

            return Response(response_data)

        except Exception as e:
            error_detail = traceback.format_exc()
            print(f"Push sales error: {error_detail}")
            return Response(
                {"success": False, "error": str(e), "traceback": error_detail},
                status=500,
            )

    @action(detail=False, methods=["post"])
    def push_returns(self, request):
        """Receive returns from POS"""
        try:
            store_id = request.data.get("store_id")
            returns_data = request.data.get("returns", [])

            if not returns_data:
                return Response({"success": True, "message": "No returns to sync"})

            synced_count = 0
            error_count = 0
            errors = []

            with transaction.atomic():
                for return_data in returns_data:
                    try:
                        cashier = User.objects.filter(
                            id=return_data["cashier_id"]
                        ).first()

                        if not cashier:
                            error_msg = (
                                f"Cashier not found: {return_data['cashier_id']}"
                            )
                            print(error_msg)
                            errors.append(
                                {
                                    "return": return_data.get("return_number"),
                                    "error": error_msg,
                                }
                            )
                            error_count += 1
                            continue

                        # Find sale
                        sale = Sale.objects.filter(
                            sale_number=return_data["sale_number"]
                        ).first()

                        if not sale:
                            error_msg = f"Sale not found: {return_data['sale_number']}"
                            print(error_msg)
                            errors.append(
                                {
                                    "return": return_data.get("return_number"),
                                    "error": error_msg,
                                }
                            )
                            error_count += 1
                            continue

                        # Create or update return
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

                        # Process return items
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
                                    "return_reason": item_data.get("return_reason", ""),
                                    "unit_price": item_data["unit_price"],
                                    "total_price": item_data["total_price"],
                                },
                            )

                        synced_count += 1
                        print(f"Synced return: {return_data['return_number']}")

                    except Exception as e:
                        error_count += 1
                        error_msg = f"Error syncing return {return_data.get('return_number')}: {str(e)}"
                        print(error_msg)
                        errors.append(
                            {
                                "return": return_data.get("return_number"),
                                "error": str(e),
                            }
                        )
                        traceback.print_exc()

            response_data = {
                "success": True,
                "synced_count": synced_count,
                "error_count": error_count,
                "message": f"Synced {synced_count} returns, {error_count} errors",
            }

            if errors:
                response_data["errors"] = errors

            return Response(response_data)

        except Exception as e:
            error_detail = traceback.format_exc()
            print(f"Push returns error: {error_detail}")
            return Response(
                {"success": False, "error": str(e), "traceback": error_detail},
                status=500,
            )
