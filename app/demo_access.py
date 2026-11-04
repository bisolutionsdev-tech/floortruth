"""Optional shared-password gate for the hosted synthetic demo.

This is a single shared credential, not individual identity or authorization.
Sessions and login throttling are local to the service instance.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from urllib.parse import parse_qs, urlsplit

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

COOKIE_NAME = "floortruth_demo_session"
SESSION_SECONDS = 8 * 60 * 60
LOGIN_WINDOW_SECONDS = 5 * 60
LOGIN_ATTEMPTS = 10
_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()

LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FloorTruth demo access</title><style>
body{font:16px system-ui;background:#101c26;color:#ecf6f2;display:grid;place-items:center;min-height:90vh;margin:0}
main{width:min(28rem,85vw);padding:2rem;background:#1b3039;border-radius:1rem}
label,input,button{display:block;width:100%;box-sizing:border-box}input,button{padding:.8rem;margin-top:.6rem;border-radius:.4rem;border:1px solid #91aaa3;font:inherit}
button{background:#a7e8ca;color:#10231d;font-weight:700;cursor:pointer}p{line-height:1.5}
</style></head><body><main><h1>FloorTruth demo</h1>
<p>Enter the shared demo password to explore synthetic examples.</p>
<form action="/demo-login" method="post"><label for="password">Demo password</label>
<input id="password" name="password" type="password" autocomplete="current-password" required autofocus>
<button type="submit">Continue</button></form></main></body></html>"""


def _signing_key(secret: str, password: str) -> bytes:
    return hmac.new(secret.encode(), password.encode(), hashlib.sha256).digest()


def _session(key: bytes) -> str:
    payload = f"{int(time.time()) + SESSION_SECONDS}.{secrets.token_urlsafe(24)}"
    signature = hmac.new(key, payload.encode(), hashlib.sha256).digest()
    return payload + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")


def _valid_session(value: str, key: bytes) -> bool:
    try:
        expiry, nonce, signature = value.split(".")
        if not nonce or int(expiry) <= time.time():
            return False
        payload = f"{expiry}.{nonce}"
        expected = base64.urlsafe_b64encode(hmac.new(key, payload.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    try:
        parsed = urlsplit(origin)
        return parsed.scheme in ("http", "https") and parsed.netloc.lower() == request.headers.get("host", "").lower()
    except ValueError:
        return False


def _limited(client: str) -> bool:
    now = time.monotonic()
    with _lock:
        # Expire inactive addresses to avoid keeping them forever.
        for address in list(_attempts):
            if not _attempts[address] or now - _attempts[address][-1] >= LOGIN_WINDOW_SECONDS:
                del _attempts[address]
        attempts = _attempts[client]
        while attempts and now - attempts[0] >= LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= LOGIN_ATTEMPTS:
            return True
        attempts.append(now)
        return False


class DemoAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        enabled = os.getenv("FLOORTRUTH_DEMO_ACCESS", "false").strip().lower()
        if enabled in ("", "false"):
            return await call_next(request)
        if enabled != "true":
            return JSONResponse({"detail": "Demo access is not configured"}, status_code=503,
                                headers={"Cache-Control": "no-store"})
        password = os.getenv("FLOORTRUTH_DEMO_PASSWORD", "")
        secret = os.getenv("FLOORTRUTH_SESSION_SECRET", "")
        if len(password) < 12 or len(secret) < 32 or password == secret:
            return JSONResponse({"detail": "Demo access is not configured"}, status_code=503,
                                headers={"Cache-Control": "no-store"})
        if request.method not in ("GET", "HEAD", "OPTIONS") and not _same_origin(request):
            return JSONResponse({"detail": "Origin rejected"}, status_code=403)
        key = _signing_key(secret, password)
        if request.url.path == "/demo-login":
            if request.method == "GET":
                return HTMLResponse(LOGIN_PAGE, headers={"Cache-Control": "no-store"})
            if request.method != "POST":
                return JSONResponse({"detail": "Method not allowed"}, status_code=405)
            if _limited(request.client.host if request.client else "unknown"):
                return HTMLResponse("Too many attempts. Try again later.", status_code=429,
                                    headers={"Cache-Control": "no-store", "Retry-After": str(LOGIN_WINDOW_SECONDS)})
            body = await request.body()
            if len(body) > 4096:
                return HTMLResponse("Invalid credentials", status_code=400)
            supplied = parse_qs(body.decode("utf-8", errors="replace")).get("password", [""])[0]
            if not hmac.compare_digest(supplied.encode(), password.encode()):
                return HTMLResponse("Invalid credentials. <a href='/demo-login'>Try again</a>", status_code=401,
                                    headers={"Cache-Control": "no-store"})
            response = RedirectResponse("/", status_code=303, headers={"Cache-Control": "no-store"})
            response.set_cookie(COOKIE_NAME, _session(key), max_age=SESSION_SECONDS, secure=True,
                                httponly=True, samesite="strict", path="/")
            return response
        authenticated = _valid_session(request.cookies.get(COOKIE_NAME, ""), key)
        # Health probes need only a non-sensitive liveness signal. Configuration
        # was checked above, so a misconfigured gate still fails closed.
        if request.url.path == "/api/health" and request.method == "HEAD":
            return Response(status_code=200, media_type="application/json",
                            headers={"Cache-Control": "no-store"})
        if not authenticated:
            if request.url.path == "/api/health" and request.method == "GET":
                return JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
            if request.url.path.startswith("/api/"):
                return JSONResponse({"detail": "Demo password required"}, status_code=401,
                                    headers={"Cache-Control": "no-store"})
            return RedirectResponse("/demo-login", status_code=303, headers={"Cache-Control": "no-store"})
        return await call_next(request)
