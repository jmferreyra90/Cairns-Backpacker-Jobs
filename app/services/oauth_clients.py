"""OAuth registrations. Never put client secrets or access tokens in HTML."""
import os

from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv

load_dotenv()
oauth = OAuth()

if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
    oauth.register(
        name="google",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email https://www.googleapis.com/auth/gmail.send",
            "code_challenge_method": "S256",
        },
    )

if os.getenv("MICROSOFT_CLIENT_ID") and os.getenv("MICROSOFT_CLIENT_SECRET"):
    oauth.register(
        name="microsoft",
        client_id=os.environ["MICROSOFT_CLIENT_ID"],
        client_secret=os.environ["MICROSOFT_CLIENT_SECRET"],
        server_metadata_url=(
            "https://login.microsoftonline.com/consumers/v2.0/"
            ".well-known/openid-configuration"
        ),
        client_kwargs={
            "scope": "openid email profile User.Read Mail.Send",
            "code_challenge_method": "S256",
        },
    )
