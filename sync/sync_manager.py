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
        data = self.api.initial_sync()

        if not data:
            print("Initial sync failed")
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

    def full_sync(self):
        if not self.api.test_connection():
            print("Server unreachable, skipping sync")
            return False

        self.pull_from_server()
        return True

    def pull_from_server(self):
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

    def _sync_users(self, users_data):
        for user_data in users_data:
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

        print(f"\nSynced {len(users_data)} users")
