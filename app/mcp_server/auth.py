from jose import JWTError, jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier

from app.config import settings


class JWTTokenVerifier(TokenVerifier):
    """Accepts the same JWTs devboard-core issues to the web app."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            return AccessToken(
                token=token, client_id="devboard", scopes=[],
                expires_at=payload.get("exp"), subject=payload["sub"],
            )
        except (JWTError, KeyError):
            return None