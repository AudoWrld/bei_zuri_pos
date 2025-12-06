from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from products.models import Product, Category, Brand, Barcode
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

            return self.pull_from_server()
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

    def _sync_categories(self, categories_data):
        try:
            if not categories_data:
                print("No category data to sync")
                return

            synced_count = 0
            error_count = 0

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

            print(f"Synced {synced_count} categories, {error_count} errors")
        except Exception as e:
            print(f"Sync categories error: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _sync_brands(self, brands_data):
        try:
            if not brands_data:
                print("No brand data to sync")
                return

            synced_count = 0
            error_count = 0

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

            print(f"Synced {synced_count} brands, {error_count} errors")
        except Exception as e:
            print(f"Sync brands error: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _sync_products(self, products_data):
        try:
            if not products_data:
                print("No product data to sync")
                return

            synced_count = 0
            error_count = 0

            for product_data in products_data:
                try:
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

            print(f"Synced {synced_count} products, {error_count} errors")
        except Exception as e:
            print(f"Sync products error: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _sync_users(self, users_data):
        try:
            if not users_data:
                print("No user data to sync")
                return

            synced_count = 0
            error_count = 0

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

            print(f"Synced {synced_count} users, {error_count} errors")
        except Exception as e:
            print(f"Sync users error: {e}")
            import traceback

            traceback.print_exc()
            raise
