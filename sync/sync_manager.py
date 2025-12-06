from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
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
                self._sync_users(data.get("users", []))

                SyncLog.objects.create(
                    sync_type="initial",
                    status="success",
                    records_count=len(data.get("users", [])),
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
                self._sync_users(data.get("users", []))

                SyncLog.objects.create(
                    sync_type="pull",
                    status="success",
                    records_count=len(data.get("users", [])),
                    completed_at=timezone.now(),
                )

            print(f"Pulled updates: {len(data.get('users', []))} users")
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

            print(f"\nSynced {synced_count} users successfully, {error_count} errors")
        except Exception as e:
            print(f"Sync users error: {e}")
            import traceback

            traceback.print_exc()
            raise
