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


def needs_migration():
    try:
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)

        return bool(plan)
    except Exception as e:
        print(f"Error checking migrations: {e}")
        return True


def run_migrations():
    print("Checking for pending migrations...")
    try:
        if not needs_migration():
            print("No migrations needed")
            return True

        print("Running database migrations...")
        from django.core.management import call_command

        call_command("migrate", interactive=False, verbosity=1)
        print("Migrations completed successfully")
        return True
    except Exception as e:
        print(f"Migration error: {e}")
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


def main():
    port = get_available_port()

    server_thread = threading.Thread(target=start_django, args=(port,), daemon=True)
    server_thread.start()

    for i in range(30):
        if is_port_in_use(port):
            break
        time.sleep(0.1)
    else:
        print("Failed to start Django server")
        return

    print(f"Server started on http://127.0.0.1:{port}")

    window = webview.create_window(
        "BeiZuri POS",
        f"http://127.0.0.1:{port}/splash/",
        width=1480,
        height=1040,
        min_size=(1480, 1040),
        resizable=True,
        fullscreen=False,
        text_select=True,
    )

    def redirect_to_home():
        time.sleep(2)
        window.load_url(f"http://127.0.0.1:{port}")

    threading.Thread(target=redirect_to_home, daemon=True).start()

    webview.start()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
