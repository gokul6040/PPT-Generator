"""Single-port reverse proxy for unified container deploy.

Routes:
  /health, /chat/*, /download/*, /api/messages -> FastAPI (127.0.0.1:8000)
  everything else                             -> Next.js (127.0.0.1:3000)
"""
from __future__ import annotations

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

API = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:3000"

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "content-encoding",
}


def _upstream_base(path: str) -> str:
    if path == "health" or path.startswith(("chat", "download", "api/messages")):
        return API
    return WEB


def clean_request_headers(headers) -> dict[str, str]:
    cleaned = {
        k: v
        for k, v in headers.items()
        if k.lower() not in HOP_BY_HOP_HEADERS
    }
    cleaned["accept-encoding"] = "identity"
    return cleaned


def clean_response_headers(headers) -> dict[str, str]:
    return {
        k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS
    }


async def proxy(request: Request) -> Response:
    path = request.url.path.lstrip("/")
    base = _upstream_base(path)
    url = f"{base}/{path}" if path else f"{base}/"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = clean_request_headers(request.headers)

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        upstream = await client.request(
            request.method,
            url,
            headers=headers,
            content=await request.body(),
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=clean_response_headers(upstream.headers),
    )


app = Starlette(
    routes=[
        Route("/", proxy, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]),
        Route("/{path:path}", proxy, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]),
    ],
)
