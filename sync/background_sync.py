import threading
import time
from django.utils import timezone
from django.conf import settings
from .sync_manager import SyncManager


class BackgroundSync:
    def __init__(self, interval=300):
        self.interval = interval
        self.running = False
        self.thread = None
        self.sync_manager = SyncManager()

    def start(self):
        if (
            not settings.IS_DESKTOP
            or not settings.ENABLE_SYNC
            or not settings.SERVER_API_URL
        ):
            print("Sync disabled or not configured")
            return

        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.thread.start()
            print(f"Background sync started (interval: {self.interval}s)")

    def stop(self):
        self.running = False
        print("Background sync stopped")

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
                    first_run = False

                print(f"[{timezone.now().strftime('%H:%M:%S')}] Starting sync...")

                if self.sync_manager.api.test_connection():
                    self.sync_manager.full_sync()
                    print(f"[{timezone.now().strftime('%H:%M:%S')}] Sync complete")
                else:
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] Server unreachable, working offline"
                    )

            except Exception as e:
                print(f"Sync error: {e}")

            time.sleep(self.interval)


sync_service = BackgroundSync(
    interval=settings.SYNC_INTERVAL if settings.IS_DESKTOP else 300
)
