import threading
import time
from django.utils import timezone
from django.conf import settings
from .sync_manager import SyncManager


class BackgroundSync:
    def __init__(self, interval=30):
        self.interval = interval
        self.running = False
        self.thread = None
        self.sync_manager = None

    def start(self):
        if (
            not settings.IS_DESKTOP
            or not settings.ENABLE_SYNC
            or not settings.SERVER_API_URL
        ):
            print("Sync disabled or not configured")
            return

        if not self.running:
            self.sync_manager = SyncManager()
            self.running = True
            self.thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.thread.start()
            print(f"Background sync started (interval: {self.interval}s)")

    def stop(self):
        self.running = False
        print("Background sync stopped")

    def sync_now(self):
        """Trigger immediate sync (called from views or on app close)"""
        if self.sync_manager:
            try:
                print(
                    f"[{timezone.now().strftime('%H:%M:%S')}] Manual sync triggered..."
                )
                return self.sync_manager.full_sync()
            except Exception as e:
                print(f"Manual sync error: {e}")
                return False
        return False

    def _sync_loop(self):
        first_run = True

        while self.running:
            try:
                if first_run:
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] Checking for initial sync..."
                    )
                    from .models import SyncLog

                    if not SyncLog.objects.filter(
                        sync_type="initial", status="success"
                    ).exists():
                        print("Running initial sync...")
                        self.sync_manager.initial_setup()
                    else:
                        print("Initial sync already completed")

                    if self.sync_manager.api.test_connection():
                        print(
                            f"[{timezone.now().strftime('%H:%M:%S')}] Running first sync..."
                        )
                        self.sync_manager.full_sync()

                    first_run = False

                time.sleep(self.interval)

                if self.sync_manager.api.test_connection():
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] Running scheduled sync..."
                    )

                    self.sync_manager.push_sales_to_server()
                    self.sync_manager.push_returns_to_server()

                    self.sync_manager.pull_from_server()

                    self.sync_manager.pull_sales_from_server()
                    self.sync_manager.pull_returns_from_server()

                    print(f"[{timezone.now().strftime('%H:%M:%S')}] ✓ Sync completed")
                else:
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] Server unreachable, working offline"
                    )

            except Exception as e:
                print(f"Sync error: {e}")
                import traceback

                traceback.print_exc()


sync_service = BackgroundSync(
    interval=(
        settings.SYNC_INTERVAL
        if hasattr(settings, "SYNC_INTERVAL") and settings.IS_DESKTOP
        else 30
    )
)
