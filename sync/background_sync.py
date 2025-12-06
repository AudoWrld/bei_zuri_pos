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
        self.initial_sync_done = False

    def start(self):
        """Start the background sync service"""
        if (
            not settings.IS_DESKTOP
            or not settings.ENABLE_SYNC
            or not settings.SERVER_API_URL
        ):
            print("Sync disabled or not configured")
            return

        if self.running:
            print("Background sync already running")
            return

        print(f"Starting background sync service (interval: {self.interval}s)...")
        self.running = True
        self.sync_manager = SyncManager()
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()
        print("Background sync service started")

    def stop(self):
        """Stop the background sync service"""
        self.running = False
        if self.thread and self.thread.is_alive():
            print("Stopping background sync...")
            self.thread.join(timeout=5)
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
                import traceback

                traceback.print_exc()
                return False
        return False

    def _sync_loop(self):
        """Main sync loop running in background thread"""
        import django

        try:
            django.setup()
        except:
            pass

        print(f"[{timezone.now().strftime('%H:%M:%S')}] Background sync loop started")

        time.sleep(5)

        while self.running:
            try:
                if not self.initial_sync_done:
                    from .models import SyncLog

                    if not SyncLog.objects.filter(
                        sync_type="initial", status="success"
                    ).exists():
                        print(
                            f"[{timezone.now().strftime('%H:%M:%S')}] Running initial sync..."
                        )
                        if self.sync_manager.initial_setup():
                            self.initial_sync_done = True
                            print(
                                f"[{timezone.now().strftime('%H:%M:%S')}] Initial sync completed"
                            )
                        else:
                            print(
                                f"[{timezone.now().strftime('%H:%M:%S')}] Initial sync failed, will retry"
                            )
                            time.sleep(self.interval)
                            continue
                    else:
                        self.initial_sync_done = True
                        print(
                            f"[{timezone.now().strftime('%H:%M:%S')}] Initial sync already completed"
                        )

                if not self.sync_manager.api.test_connection():
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] Server unreachable, working offline"
                    )
                    time.sleep(self.interval)
                    continue

                print(
                    f"[{timezone.now().strftime('%H:%M:%S')}] Running scheduled sync..."
                )

                push_success = True
                if not self.sync_manager.push_sales_to_server():
                    push_success = False
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] ⚠ Failed to push sales"
                    )

                if not self.sync_manager.push_returns_to_server():
                    push_success = False
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] ⚠ Failed to push returns"
                    )

                pull_success = True
                if not self.sync_manager.pull_from_server():
                    pull_success = False
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] ⚠ Failed to pull updates"
                    )

                if not self.sync_manager.pull_sales_from_server():
                    pull_success = False
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] ⚠ Failed to pull sales"
                    )

                if not self.sync_manager.pull_returns_from_server():
                    pull_success = False
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] ⚠ Failed to pull returns"
                    )

                if push_success and pull_success:
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] ✓ Sync completed successfully"
                    )
                else:
                    print(
                        f"[{timezone.now().strftime('%H:%M:%S')}] ⚠ Sync completed with errors"
                    )

            except Exception as e:
                print(f"[{timezone.now().strftime('%H:%M:%S')}] Sync error: {e}")
                import traceback

                traceback.print_exc()

            time.sleep(self.interval)

        print(f"[{timezone.now().strftime('%H:%M:%S')}] Background sync loop ended")


sync_service = BackgroundSync(
    interval=getattr(settings, "SYNC_INTERVAL", 30) if settings.IS_DESKTOP else 30
)
