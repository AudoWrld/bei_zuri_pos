import requests
from django.conf import settings
from django.utils import timezone


class ServerAPI:
    def __init__(self):
        self.base_url = settings.SERVER_API_URL
        self.api_token = settings.SERVER_API_TOKEN
        self.store_id = settings.STORE_ID

    def get_headers(self):
        return {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }

    def test_connection(self):
        try:
            response = requests.get(
                f"{self.base_url}/api/sync/health/",
                headers=self.get_headers(),
                timeout=5,
            )
            return response.status_code == 200
        except:
            return False

    def initial_sync(self):
        try:
            response = requests.post(
                f"{self.base_url}/api/sync/initial_sync/",
                json={"store_id": self.store_id},
                headers=self.get_headers(),
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Initial sync error: {e}")
            return None

    def pull_updates(self, last_sync):
        try:
            response = requests.get(
                f"{self.base_url}/api/sync/pull_updates/",
                params={"since": last_sync, "store_id": self.store_id},
                headers=self.get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Pull error: {e}")
            return None

    def push_sales(self, sales_data):
        try:
            response = requests.post(
                f"{self.base_url}/api/sync/push_sales/",
                json={"store_id": self.store_id, "sales": sales_data},
                headers=self.get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Push sales error: {e}")
            return None

    def push_returns(self, returns_data):
        try:
            response = requests.post(
                f"{self.base_url}/api/sync/push_returns/",
                json={"store_id": self.store_id, "returns": returns_data},
                headers=self.get_headers(),
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Push returns error: {e}")
            return None
