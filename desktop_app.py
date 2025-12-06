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
    print("Running database migrations...")
    try:
        from django.core.management import call_command

        call_command("makemigrations", interactive=False, verbosity=1)
        call_command("migrate", interactive=False, verbosity=1)
        print("Migrations completed successfully")
        return True
    except Exception as e:
        print(f"Migration error: {e}")
        import traceback

        traceback.print_exc()
        return False


def initial_sync():
    try:
        from sync.models import SyncLog
        from sync.sync_manager import SyncManager

        if SyncLog.objects.filter(sync_type="initial", status="success").exists():
            print("Initial sync already completed, skipping...")
            return True

        print("Running initial sync from server...")
        sync_manager = SyncManager()
        result = sync_manager.initial_setup()

        if result:
            print("Initial sync completed successfully")
        else:
            print("Initial sync failed")

        return result
    except Exception as e:
        print(f"Error during initial sync: {e}")
        import traceback

        traceback.print_exc()
        return False


def start_background_sync():
    try:
        from django.conf import settings

        if settings.IS_DESKTOP and settings.ENABLE_SYNC:
            from sync.background_sync import sync_service

            print("Starting background sync service...")
            sync_service.start()
    except Exception as e:
        print(f"Error starting background sync: {e}")
        import traceback

        traceback.print_exc()


def start_django(port):
    if not is_port_in_use(port):
        try:
            import django

            django.setup()

            if not run_migrations():
                print("Warning: Migrations failed, continuing anyway...")
                return

            initial_sync()

            start_background_sync()

            from waitress import serve
            from django.core.wsgi import get_wsgi_application

            application = get_wsgi_application()
            print(f"Starting server on port {port}...")
            serve(application, host="127.0.0.1", port=port, threads=4)
        except Exception as e:
            print(f"Error starting server: {e}")
            import traceback

            traceback.print_exc()


def wait_for_server(port, timeout=120):
    import requests

    start_time = time.time()

    while time.time() - start_time < timeout:
        if is_port_in_use(port):
            try:
                response = requests.get(f"http://127.0.0.1:{port}/splash/", timeout=2)
                if response.status_code == 200:
                    return True
            except:
                pass
        time.sleep(0.5)

    return False


def main():
    port = get_available_port()

    server_thread = threading.Thread(target=start_django, args=(port,), daemon=True)
    server_thread.start()

    print("Waiting for server to be ready...")
    if not wait_for_server(port, timeout=120):
        print("Failed to start Django server")
        return

    print(f"Server ready on http://127.0.0.1:{port}")

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
        time.sleep(3)
        window.load_url(f"http://127.0.0.1:{port}")

    threading.Thread(target=redirect_to_home, daemon=True).start()

    webview.start()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
