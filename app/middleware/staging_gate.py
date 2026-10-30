"""Small preview-only Basic authentication gate. Never use for real user auth."""
import base64
import binascii
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse


class StagingGateMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, username: str, password: str):
        super().__init__(app)
        self.username = username
        self.password = password

    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        valid = False
        if authorization.startswith("Basic "):
            try:
                raw = base64.b64decode(authorization[6:], validate=True).decode("utf-8")
                username, password = raw.split(":", 1)
                valid = (
                    secrets.compare_digest(username, self.username)
                    and secrets.compare_digest(password, self.password)
                )
            except (ValueError, UnicodeDecodeError, binascii.Error):
                pass
        if not valid:
            return PlainTextResponse(
                "Private development preview. / Vista previa privada.",
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="Cairns staging"',
                    "Cache-Control": "no-store",
                },
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response
