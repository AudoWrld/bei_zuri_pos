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
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from sync.models import SyncLog
from sync.background_sync import sync_service
from sales.models import Sale, Return
from django.conf import settings

User = get_user_model()
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

    @action(detail=False, methods=["post"])
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
            brands = Brand.objects.filter(updated_at__gte=since, is_active=True)
            products = Product.objects.filter(updated_at__gte=since, is_active=True)

            has_updates = (
                users.exists()
                or categories.exists()
                or brands.exists()
                or products.exists()
            )

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


@staff_member_required
@require_http_methods(["GET"])
def sync_status(request):
    """Comprehensive sync status endpoint"""
    sync_running = sync_service.running if sync_service else False

    recent_logs = SyncLog.objects.all()[:10]
    logs_data = []
    for log in recent_logs:
        logs_data.append(
            {
                "type": log.sync_type,
                "status": log.status,
                "records": log.records_count,
                "error": log.error_message,
                "time": log.completed_at.isoformat() if log.completed_at else None,
            }
        )

    unsynced_sales = Sale.objects.filter(
        completed_at__isnull=False, synced_at__isnull=True
    ).count()

    unsynced_returns = Return.objects.filter(synced_at__isnull=True).count()

    last_syncs = {}
    for sync_type in [
        "initial",
        "pull",
        "push_sales",
        "push_returns",
        "pull_sales",
        "pull_returns",
    ]:
        last = (
            SyncLog.objects.filter(sync_type=sync_type, status="success")
            .order_by("-completed_at")
            .first()
        )

        last_syncs[sync_type] = {
            "time": (
                last.completed_at.isoformat() if last and last.completed_at else None
            ),
            "records": last.records_count if last else 0,
        }

    # Count synced records
    synced_products = Product.objects.filter(server_id__isnull=False).count()
    synced_categories = Category.objects.filter(server_id__isnull=False).count()
    synced_brands = Brand.objects.filter(server_id__isnull=False).count()
    synced_users = User.objects.filter(server_id__isnull=False).count()

    total_sales = Sale.objects.filter(completed_at__isnull=False).count()
    synced_sales = Sale.objects.filter(synced_at__isnull=False).count()

    total_returns = Return.objects.count()
    synced_returns = Return.objects.filter(synced_at__isnull=False).count()

    # Server connection test
    try:
        from sync.api_client import ServerAPI

        api = ServerAPI()
        server_reachable = api.test_connection()
    except Exception as e:
        server_reachable = False

    return JsonResponse(
        {
            "sync_enabled": (
                settings.ENABLE_SYNC if hasattr(settings, "ENABLE_SYNC") else False
            ),
            "is_desktop": (
                settings.IS_DESKTOP if hasattr(settings, "IS_DESKTOP") else False
            ),
            "background_sync_running": sync_running,
            "server_reachable": server_reachable,
            "server_url": (
                settings.SERVER_API_URL if hasattr(settings, "SERVER_API_URL") else None
            ),
            "unsynced": {"sales": unsynced_sales, "returns": unsynced_returns},
            "synced_from_server": {
                "products": synced_products,
                "categories": synced_categories,
                "brands": synced_brands,
                "users": synced_users,
            },
            "sales_stats": {
                "total": total_sales,
                "synced": synced_sales,
                "percentage": round(
                    (synced_sales / total_sales * 100) if total_sales > 0 else 0, 2
                ),
            },
            "returns_stats": {
                "total": total_returns,
                "synced": synced_returns,
                "percentage": round(
                    (synced_returns / total_returns * 100) if total_returns > 0 else 0,
                    2,
                ),
            },
            "last_syncs": last_syncs,
            "recent_logs": logs_data,
            "current_time": timezone.now().isoformat(),
        }
    )


@staff_member_required
@require_http_methods(["POST"])
def trigger_sync(request):
    """Manually trigger a sync"""
    try:
        if not sync_service:
            return JsonResponse(
                {"success": False, "error": "Sync service not initialized"}, status=500
            )

        result = sync_service.sync_now()

        return JsonResponse(
            {
                "success": result,
                "message": "Sync completed" if result else "Sync failed",
                "timestamp": timezone.now().isoformat(),
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@staff_member_required
@require_http_methods(["GET"])
def check_server_connection(request):
    """Test server connection"""
    try:
        from sync.api_client import ServerAPI

        api = ServerAPI()

        reachable = api.test_connection()

        return JsonResponse(
            {
                "reachable": reachable,
                "server_url": (
                    settings.SERVER_API_URL
                    if hasattr(settings, "SERVER_API_URL")
                    else None
                ),
                "timestamp": timezone.now().isoformat(),
            }
        )
    except Exception as e:
        import traceback

        return JsonResponse(
            {"reachable": False, "error": str(e), "traceback": traceback.format_exc()},
            status=500,
        )
