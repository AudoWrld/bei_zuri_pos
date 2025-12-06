from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from products.models import Product, Category, Brand, Barcode
from sales.models import Sale, SaleItem, Return, ReturnItem
from .api_client import ServerAPI
from .models import SyncLog

User = get_user_model()


class SyncManager:
    def __init__(self):
        self.api = ServerAPI()

    def initial_setup(self):
        print("Starting initial sync from server...")
        try:
            data = self.api.initial_sync()

            if not data:
                print("Initial sync failed - no data received")
                return False

            with transaction.atomic():
                self._sync_categories(data.get("categories", []))
                self._sync_brands(data.get("brands", []))
                self._sync_products(data.get("products", []))
                self._sync_users(data.get("users", []))

                total_records = (
                    len(data.get("categories", []))
                    + len(data.get("brands", []))
                    + len(data.get("products", []))
                    + len(data.get("users", []))
                )

                SyncLog.objects.create(
                    sync_type="initial",
                    status="success",
                    records_count=total_records,
                    completed_at=timezone.now(),
                )

            print("Initial sync completed successfully")
            return True
        except Exception as e:
            print(f"Initial sync error: {e}")
            import traceback

            traceback.print_exc()
            SyncLog.objects.create(
                sync_type="initial",
                status="failed",
                error_message=str(e),
                completed_at=timezone.now(),
            )
            return False

    def full_sync(self):
        try:
            if not self.api.test_connection():
                print("Server unreachable, skipping sync")
                return False

            self.push_sales_to_server()
            self.push_returns_to_server()
            self.pull_from_server()
            self.pull_sales_from_server()
            self.pull_returns_from_server()

            return True
        except Exception as e:
            print(f"Full sync error: {e}")
            import traceback

            traceback.print_exc()
            return False

    def pull_from_server(self):
        try:
            last_sync = (
                SyncLog.objects.filter(sync_type="pull", status="success")
                .order_by("-completed_at")
                .first()
            )

            last_sync_time = (
                last_sync.completed_at
                if last_sync
                else timezone.now() - timezone.timedelta(days=365)
            )

            print(f"Pulling updates since: {last_sync_time.isoformat()}")
            data = self.api.pull_updates(last_sync_time.isoformat())

            if not data:
                print("Pull failed or no data")
                return False

            if not data.get("has_updates"):
                print("No updates from server")
                return True

            with transaction.atomic():
                self._sync_categories(data.get("categories", []), check_deletions=True)
                self._sync_brands(data.get("brands", []), check_deletions=True)
                self._sync_products(
                    data.get("products", []), update_mode=True, check_deletions=True
                )
                self._sync_users(data.get("users", []), check_deletions=True)

                total_records = (
                    len(data.get("categories", []))
                    + len(data.get("brands", []))
                    + len(data.get("products", []))
                    + len(data.get("users", []))
                )

                SyncLog.objects.create(
                    sync_type="pull",
                    status="success",
                    records_count=total_records,
                    completed_at=timezone.now(),
                )

            print(f"Pulled updates: {total_records} records")
            return True
        except Exception as e:
            print(f"Pull from server error: {e}")
            import traceback

            traceback.print_exc()
            SyncLog.objects.create(
                sync_type="pull",
                status="failed",
                error_message=str(e),
                completed_at=timezone.now(),
            )
            return False

    def pull_sales_from_server(self):
        try:
            last_sync = (
                SyncLog.objects.filter(sync_type="pull_sales", status="success")
                .order_by("-completed_at")
                .first()
            )

            last_sync_time = (
                last_sync.completed_at
                if last_sync
                else timezone.now() - timezone.timedelta(days=30)
            )

            print(f"Pulling sales since: {last_sync_time.isoformat()}")
            data = self.api.pull_sales(last_sync_time.isoformat())

            if not data or not data.get("sales"):
                print("No new sales from server")
                return True

            synced_count = 0
            with transaction.atomic():
                for sale_data in data.get("sales", []):
                    if Sale.objects.filter(
                        sale_number=sale_data["sale_number"]
                    ).exists():
                        continue

                    try:
                        cashier = User.objects.filter(
                            server_id=sale_data["cashier_id"]
                        ).first()
                        if not cashier:
                            print(f"Cashier not found: {sale_data['cashier_id']}")
                            continue

                        sale = Sale.objects.create(
                            sale_number=sale_data["sale_number"],
                            sale_type=sale_data["sale_type"],
                            cashier=cashier,
                            total_amount=sale_data["total_amount"],
                            discount_amount=sale_data.get("discount_amount", 0),
                            final_amount=sale_data["final_amount"],
                            payment_method=sale_data["payment_method"],
                            money_received=sale_data.get("money_received"),
                            change_amount=sale_data.get("change_amount"),
                            notes=sale_data.get("notes", ""),
                            created_at=sale_data["created_at"],
                            completed_at=sale_data["completed_at"],
                            synced_at=timezone.now(),
                        )

                        for item_data in sale_data.get("items", []):
                            product = Product.objects.filter(
                                server_id=item_data["product_id"]
                            ).first()
                            if not product:
                                continue

                            SaleItem.objects.create(
                                sale=sale,
                                product=product,
                                quantity=item_data["quantity"],
                                unit_price=item_data["unit_price"],
                                discount_amount=item_data.get("discount_amount", 0),
                                total_amount=item_data["total_amount"],
                            )

                        synced_count += 1
                        print(f"  Pulled sale: {sale.sale_number}")

                    except Exception as e:
                        print(f"Error pulling sale {sale_data.get('sale_number')}: {e}")
                        continue

                SyncLog.objects.create(
                    sync_type="pull_sales",
                    status="success",
                    records_count=synced_count,
                    completed_at=timezone.now(),
                )

            print(f"Pulled {synced_count} sales from server")
            return True

        except Exception as e:
            print(f"Pull sales error: {e}")
            import traceback

            traceback.print_exc()
            return False

    def pull_returns_from_server(self):
        try:
            last_sync = (
                SyncLog.objects.filter(sync_type="pull_returns", status="success")
                .order_by("-completed_at")
                .first()
            )

            last_sync_time = (
                last_sync.completed_at
                if last_sync
                else timezone.now() - timezone.timedelta(days=30)
            )

            print(f"Pulling returns since: {last_sync_time.isoformat()}")
            data = self.api.pull_returns(last_sync_time.isoformat())

            if not data or not data.get("returns"):
                print("No new returns from server")
                return True

            synced_count = 0
            with transaction.atomic():
                for return_data in data.get("returns", []):
                    if Return.objects.filter(
                        return_number=return_data["return_number"]
                    ).exists():
                        continue

                    try:
                        cashier = User.objects.filter(
                            server_id=return_data["cashier_id"]
                        ).first()
                        sale = Sale.objects.filter(
                            sale_number=return_data["sale_number"]
                        ).first()

                        if not cashier or not sale:
                            print(
                                f"Cashier or sale not found for return {return_data['return_number']}"
                            )
                            continue

                        return_obj = Return.objects.create(
                            return_number=return_data["return_number"],
                            sale=sale,
                            cashier=cashier,
                            total_return_amount=return_data["total_return_amount"],
                            notes=return_data.get("notes", ""),
                            created_at=return_data["created_at"],
                            synced_at=timezone.now(),
                        )

                        for item_data in return_data.get("items", []):
                            sale_item = SaleItem.objects.filter(
                                sale=sale, product__server_id=item_data["product_id"]
                            ).first()

                            if not sale_item:
                                continue

                            ReturnItem.objects.create(
                                return_fk=return_obj,
                                sale_item=sale_item,
                                quantity=item_data["quantity"],
                                return_reason=item_data.get("return_reason", ""),
                                unit_price=item_data["unit_price"],
                                total_price=item_data["total_price"],
                            )

                        synced_count += 1
                        print(f"  Pulled return: {return_obj.return_number}")

                    except Exception as e:
                        print(
                            f"Error pulling return {return_data.get('return_number')}: {e}"
                        )
                        continue

                SyncLog.objects.create(
                    sync_type="pull_returns",
                    status="success",
                    records_count=synced_count,
                    completed_at=timezone.now(),
                )

            print(f"Pulled {synced_count} returns from server")
            return True

        except Exception as e:
            print(f"Pull returns error: {e}")
            import traceback

            traceback.print_exc()
            return False

    def push_sales_to_server(self):
        try:
            unsynced_sales = (
                Sale.objects.filter(completed_at__isnull=False, synced_at__isnull=True)
                .select_related("cashier")
                .prefetch_related("items__product")
            )

            if not unsynced_sales.exists():
                print("No sales to push")
                return True

            sales_data = []
            for sale in unsynced_sales:
                items_data = []
                for item in sale.items.all():
                    items_data.append(
                        {
                            "product_id": (
                                item.product.server_id
                                if item.product.server_id
                                else item.product.id
                            ),
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
                        "cashier_id": (
                            sale.cashier.server_id
                            if sale.cashier.server_id
                            else sale.cashier.id
                        ),
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

            print(f"Pushing {len(sales_data)} sales to server...")
            result = self.api.push_sales(sales_data)

            if result and result.get("success"):
                with transaction.atomic():
                    unsynced_sales.update(synced_at=timezone.now())

                    SyncLog.objects.create(
                        sync_type="push_sales",
                        status="success",
                        records_count=len(sales_data),
                        completed_at=timezone.now(),
                    )

                print(f"Successfully pushed {len(sales_data)} sales")
                return True
            else:
                print("Failed to push sales to server")
                SyncLog.objects.create(
                    sync_type="push_sales",
                    status="failed",
                    error_message="Server returned failure",
                    completed_at=timezone.now(),
                )
                return False

        except Exception as e:
            print(f"Push sales error: {e}")
            import traceback

            traceback.print_exc()
            SyncLog.objects.create(
                sync_type="push_sales",
                status="failed",
                error_message=str(e),
                completed_at=timezone.now(),
            )
            return False

    def push_returns_to_server(self):
        try:
            unsynced_returns = (
                Return.objects.filter(synced_at__isnull=True)
                .select_related("cashier", "sale")
                .prefetch_related("items__sale_item__product")
            )

            if not unsynced_returns.exists():
                print("No returns to push")
                return True

            returns_data = []
            for return_obj in unsynced_returns:
                items_data = []
                for item in return_obj.items.all():
                    items_data.append(
                        {
                            "sale_item_id": item.sale_item.id,
                            "product_id": (
                                item.sale_item.product.server_id
                                if item.sale_item.product.server_id
                                else item.sale_item.product.id
                            ),
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
                        "cashier_id": (
                            return_obj.cashier.server_id
                            if return_obj.cashier.server_id
                            else return_obj.cashier.id
                        ),
                        "total_return_amount": str(return_obj.total_return_amount),
                        "notes": return_obj.notes,
                        "created_at": return_obj.created_at.isoformat(),
                        "items": items_data,
                    }
                )

            print(f"Pushing {len(returns_data)} returns to server...")
            result = self.api.push_returns(returns_data)

            if result and result.get("success"):
                with transaction.atomic():
                    unsynced_returns.update(synced_at=timezone.now())

                    SyncLog.objects.create(
                        sync_type="push_returns",
                        status="success",
                        records_count=len(returns_data),
                        completed_at=timezone.now(),
                    )

                print(f"Successfully pushed {len(returns_data)} returns")
                return True
            else:
                print("Failed to push returns to server")
                SyncLog.objects.create(
                    sync_type="push_returns",
                    status="failed",
                    error_message="Server returned failure",
                    completed_at=timezone.now(),
                )
                return False

        except Exception as e:
            print(f"Push returns error: {e}")
            import traceback

            traceback.print_exc()
            SyncLog.objects.create(
                sync_type="push_returns",
                status="failed",
                error_message=str(e),
                completed_at=timezone.now(),
            )
            return False

    def _sync_categories(self, categories_data, check_deletions=False):
        try:
            if not categories_data:
                return

            synced_count = 0
            error_count = 0
            deleted_count = 0

            if check_deletions:
                server_ids = [cat["id"] for cat in categories_data]
                local_categories = Category.objects.filter(server_id__isnull=False)

                for category in local_categories:
                    if category.server_id not in server_ids:
                        print(
                            f"  Deleting: Category {category.name} (removed from server)"
                        )
                        category.delete()
                        deleted_count += 1

            for category_data in categories_data:
                try:
                    defaults = {
                        "name": category_data["name"],
                        "description": category_data.get("description", ""),
                        "is_active": category_data["is_active"],
                        "synced_at": timezone.now(),
                    }

                    category, created = Category.objects.update_or_create(
                        server_id=category_data["id"], defaults=defaults
                    )

                    synced_count += 1
                    action = "Created" if created else "Updated"
                    print(f"  {action}: Category {category.name}")

                except Exception as e:
                    error_count += 1
                    print(
                        f"  Error syncing category {category_data.get('name', 'unknown')}: {e}"
                    )

            if synced_count > 0 or deleted_count > 0:
                print(
                    f"Synced {synced_count} categories, {deleted_count} deleted, {error_count} errors"
                )
        except Exception as e:
            print(f"Sync categories error: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _sync_brands(self, brands_data, check_deletions=False):
        try:
            if not brands_data:
                return

            synced_count = 0
            error_count = 0
            deleted_count = 0

            if check_deletions:
                server_ids = [brand["id"] for brand in brands_data]
                local_brands = Brand.objects.filter(server_id__isnull=False)

                for brand in local_brands:
                    if brand.server_id not in server_ids:
                        print(f"  Deleting: Brand {brand.name} (removed from server)")
                        brand.delete()
                        deleted_count += 1

            for brand_data in brands_data:
                try:
                    defaults = {
                        "name": brand_data["name"],
                        "description": brand_data.get("description", ""),
                        "is_active": brand_data["is_active"],
                        "synced_at": timezone.now(),
                    }

                    brand, created = Brand.objects.update_or_create(
                        server_id=brand_data["id"], defaults=defaults
                    )

                    synced_count += 1
                    action = "Created" if created else "Updated"
                    print(f"  {action}: Brand {brand.name}")

                except Exception as e:
                    error_count += 1
                    print(
                        f"  Error syncing brand {brand_data.get('name', 'unknown')}: {e}"
                    )

            if synced_count > 0 or deleted_count > 0:
                print(
                    f"Synced {synced_count} brands, {deleted_count} deleted, {error_count} errors"
                )
        except Exception as e:
            print(f"Sync brands error: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _sync_products(self, products_data, update_mode=False, check_deletions=False):
        try:
            if not products_data:
                return

            synced_count = 0
            error_count = 0
            deleted_count = 0

            if check_deletions:
                server_ids = [prod["id"] for prod in products_data]
                local_products = Product.objects.filter(server_id__isnull=False)

                for product in local_products:
                    if product.server_id not in server_ids:
                        print(
                            f"  Deleting: Product {product.name} (removed from server)"
                        )
                        product.delete()
                        deleted_count += 1

            for product_data in products_data:
                try:
                    existing_product = Product.objects.filter(
                        server_id=product_data["id"]
                    ).first()

                    if update_mode and existing_product:
                        if existing_product.quantity != product_data["quantity"]:
                            print(
                                f"  Warning: Stock mismatch for {product_data['name']}"
                            )
                            print(
                                f"    Local: {existing_product.quantity}, Server: {product_data['quantity']}"
                            )
                            print(f"    Keeping local stock, syncing other fields only")

                            product_data["quantity"] = existing_product.quantity
                            product_data["sold_count"] = existing_product.sold_count

                    category = None
                    if product_data.get("category_id"):
                        category = Category.objects.filter(
                            server_id=product_data["category_id"]
                        ).first()

                    brand = None
                    if product_data.get("brand_id"):
                        brand = Brand.objects.filter(
                            server_id=product_data["brand_id"]
                        ).first()

                    defaults = {
                        "name": product_data["name"],
                        "description": product_data.get("description", ""),
                        "category": category,
                        "brand": brand,
                        "slug": product_data["slug"],
                        "sku": product_data["sku"],
                        "cost_price": product_data["cost_price"],
                        "selling_price": product_data["selling_price"],
                        "wholesale_price": product_data.get("wholesale_price"),
                        "special_price": product_data["special_price"],
                        "quantity": product_data["quantity"],
                        "low_stock_threshold": product_data["low_stock_threshold"],
                        "weight": product_data.get("weight"),
                        "sold_count": product_data["sold_count"],
                        "is_active": product_data["is_active"],
                        "synced_at": timezone.now(),
                    }

                    product, created = Product.objects.update_or_create(
                        server_id=product_data["id"], defaults=defaults
                    )

                    if check_deletions:
                        server_barcode_ids = [
                            b["id"] for b in product_data.get("barcodes", [])
                        ]
                        local_barcodes = Barcode.objects.filter(
                            product=product, server_id__isnull=False
                        )

                        for barcode in local_barcodes:
                            if barcode.server_id not in server_barcode_ids:
                                print(f"    Deleting barcode: {barcode.barcode}")
                                barcode.delete()

                    for barcode_data in product_data.get("barcodes", []):
                        Barcode.objects.update_or_create(
                            server_id=barcode_data["id"],
                            defaults={
                                "barcode": barcode_data["barcode"],
                                "product": product,
                                "is_active": barcode_data["is_active"],
                                "synced_at": timezone.now(),
                            },
                        )

                    synced_count += 1
                    action = "Created" if created else "Updated"
                    print(f"  {action}: Product {product.name}")

                except Exception as e:
                    error_count += 1
                    print(
                        f"  Error syncing product {product_data.get('name', 'unknown')}: {e}"
                    )
                    import traceback

                    traceback.print_exc()

            if synced_count > 0 or deleted_count > 0:
                print(
                    f"Synced {synced_count} products, {deleted_count} deleted, {error_count} errors"
                )
        except Exception as e:
            print(f"Sync products error: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _sync_users(self, users_data, check_deletions=False):
        try:
            if not users_data:
                return

            synced_count = 0
            error_count = 0
            deleted_count = 0

            if check_deletions:
                server_ids = [user["id"] for user in users_data]
                local_users = User.objects.filter(server_id__isnull=False)

                for user in local_users:
                    if user.server_id not in server_ids:
                        print(f"  Deleting: User {user.username} (removed from server)")
                        user.delete()
                        deleted_count += 1

            for user_data in users_data:
                try:
                    defaults = {
                        "username": user_data["username"],
                        "email": user_data.get("email", ""),
                        "first_name": user_data.get("first_name", ""),
                        "last_name": user_data.get("last_name", ""),
                        "role": user_data["role"],
                        "phone_number": user_data.get("phone_number", ""),
                        "is_active": user_data["is_active"],
                        "is_staff": user_data.get("is_staff", False),
                        "is_superuser": user_data.get("is_superuser", False),
                        "synced_at": timezone.now(),
                    }

                    if "password" in user_data and user_data["password"]:
                        defaults["password"] = user_data["password"]

                    user, created = User.objects.update_or_create(
                        server_id=user_data["id"], defaults=defaults
                    )

                    if created and not user.has_usable_password():
                        user.set_password("changeme123")
                        user.save()

                    synced_count += 1
                    action = "Created" if created else "Updated"
                    print(f"  {action}: {user.username}")

                except Exception as e:
                    error_count += 1
                    print(
                        f"  Error syncing user {user_data.get('username', 'unknown')}: {e}"
                    )

            if synced_count > 0 or deleted_count > 0:
                print(
                    f"Synced {synced_count} users, {deleted_count} deleted, {error_count} errors"
                )
        except Exception as e:
            print(f"Sync users error: {e}")
            import traceback

            traceback.print_exc()
            raise
