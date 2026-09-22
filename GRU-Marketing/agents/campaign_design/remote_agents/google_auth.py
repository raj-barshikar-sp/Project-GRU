import google.auth
import httpx
from google.auth.transport.requests import Request


class GoogleAuth(httpx.Auth):
    """Attaches a Cloud Platform bearer token to outbound A2A HTTP calls."""

    def __init__(self):
        self.creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )

    def auth_flow(self, request):
        if not self.creds.valid:
            self.creds.refresh(Request())
        request.headers["Authorization"] = f"Bearer {self.creds.token}"
        yield request
