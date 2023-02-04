import urllib.parse
import requests
import hashlib
import base64


class HWRestClient:
    def __init__(self, username: str, password: str):
        self.endpoint = "https://api.homewizardeasyonline.com/v1/"
        self.username = username
        self.password = password

    def auth_get(self, resource: str) -> dict:
        url = urllib.parse.urljoin(self.endpoint, resource)
        encoded_pass = self.password.encode('utf-8')
        sha1_pass = hashlib.sha1(encoded_pass).hexdigest()

        encoded_token = f"{self.username}:{sha1_pass}".encode("utf-8")
        base64_token = base64.b64encode(encoded_token).decode("utf-8")

        return requests.get(url, headers={
            "Authorization": f"Basic {str(base64_token)}"
        }).json()

    def login(self):
        self.token = self.auth_get("auth/login").get("token")

    def get_account(self):
        return self.auth_get("account")

    def get_devices(self):
        return self.auth_get("auth/devices")
