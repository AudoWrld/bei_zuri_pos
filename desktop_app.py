import webview
import threading
import time
import socket
import multiprocessing
import sys
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bei_zuri_pos.settings")
os.environ.setdefault("IS_DESKTOP", "True")


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def get_available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def run_migrations():
    """Run database migrations"""
    print("Running database migrations...")
    try:
        from django.core.management import call_command

        call_command("makemigrations", interactive=False, verbosity=1)
        call_command("migrate", interactive=False, verbosity=1)
        print("✓ Migrations completed successfully")
        return True
    except Exception as e:
        print(f"✗ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_initial_sync_status():
    """Check if initial sync has been completed"""
    try:
        from sync.models import SyncLog
        return SyncLog.objects.filter(sync_type="initial", status="success").exists()
    except Exception as e:
        print(f"Error checking initial sync status: {e}")
        return False


def start_background_sync():
    """Start the background sync service"""
    try:
        from django.conf import settings

        if not settings.IS_DESKTOP or not settings.ENABLE_SYNC:
            print("Sync is disabled in settings")
            return

        if not settings.SERVER_API_URL or not settings.SERVER_API_TOKEN:
            print("⚠ Sync not configured - missing SERVER_API_URL or SERVER_API_TOKEN")
            return

        from sync.background_sync import sync_service

        print("Initializing background sync service...")
        sync_service.start()
        print("✓ Background sync service initialized")
        
    except Exception as e:
        print(f"✗ Error starting background sync: {e}")
        import traceback
        traceback.print_exc()


def start_django(port):
    """Start Django server"""
    if not is_port_in_use(port):
        try:
            import django
            django.setup()

            # Run migrations
            if not run_migrations():
                print("⚠ Warning: Migrations failed, continuing anyway...")

            # Start background sync (it will handle initial sync internally)
            start_background_sync()

            # Start the WSGI server
            from waitress import serve
            from django.core.wsgi import get_wsgi_application

            application = get_wsgi_application()
            print(f"Starting Django server on http://127.0.0.1:{port}")
            serve(application, host="127.0.0.1", port=port, threads=4)
            
        except Exception as e:
            print(f"✗ Error starting Django server: {e}")
            import traceback
            traceback.print_exc()


def wait_for_server(port, timeout=120):
    """Wait for Django server to be ready"""
    import requests

    start_time = time.time()
    print(f"Waiting for server to start on port {port}...")

    while time.time() - start_time < timeout:
        if is_port_in_use(port):
            try:
                response = requests.get(f"http://127.0.0.1:{port}/splash/", timeout=2)
                if response.status_code == 200:
                    print(f"✓ Server is ready!")
                    return True
            except:
                pass
        time.sleep(0.5)

    print(f"✗ Server failed to start within {timeout} seconds")
    return False


def main():
    """Main entry point"""
    print("=" * 60)
    print("BeiZuri POS - Starting Application")
    print("=" * 60)
    
    # Get available port
    port = get_available_port()
    print(f"Using port: {port}")

    # Start Django server in background thread
    server_thread = threading.Thread(target=start_django, args=(port,), daemon=True)
    server_thread.start()

    # Wait for server to be ready
    if not wait_for_server(port, timeout=120):
        print("Failed to start Django server. Exiting...")
        sys.exit(1)

    # Create and start webview window
    print("Creating application window...")
    window = webview.create_window(
        "BeiZuri POS",
        f"http://127.0.0.1:{port}/splash/",
        width=1480,
        height=720,
        min_size=(1480, 720),
        resizable=True,
        fullscreen=False,
        text_select=True,
    )

    def redirect_to_home():
        """Redirect from splash screen to home after delay"""
        time.sleep(3)
        window.load_url(f"http://127.0.0.1:{port}")

    # Start redirect thread
    threading.Thread(target=redirect_to_home, daemon=True).start()

    # Start webview (blocking)
    print("Starting webview...")
    webview.start()
    
    print("Application closed")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()