import webview
import threading
import time
import socket
import multiprocessing
import sys
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bei_zuri_pos.settings")


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def get_available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def start_django(port):
    if not is_port_in_use(port):
        try:
            import django

            django.setup()

            from waitress import serve
            from django.core.wsgi import get_wsgi_application

            application = get_wsgi_application()
            serve(application, host="127.0.0.1", port=port, threads=4)
        except Exception as e:
            print(f"Error starting server: {e}")


def main():
    port = get_available_port()

    server_thread = threading.Thread(target=start_django, args=(port,), daemon=True)
    server_thread.start()

    for i in range(30):
        if is_port_in_use(port):
            break
        time.sleep(0.1)

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
