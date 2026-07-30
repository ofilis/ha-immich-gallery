"""Loopback HTTP integration test for private-network Immich hosts."""

from __future__ import annotations

from typing import Any

import aiohttp
import pytest
from aiohttp import web

from custom_components.immich_gallery.api import ImmichApiClient

USER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ASSET_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.mark.asyncio
async def test_local_http_host_end_to_end() -> None:
    """A LAN-style HTTP host works without leaking the API key into URLs."""
    seen_paths: list[str] = []

    async def respond(request: web.Request) -> web.StreamResponse:
        seen_paths.append(request.path_qs)
        assert request.headers["x-api-key"] == "local-private-key"
        assert "local-private-key" not in str(request.url)

        if request.path == "/api/server/version":
            return web.json_response({"major": 3, "minor": 0, "patch": 1})
        if request.path == "/api/users/me":
            return web.json_response({"id": USER_ID, "name": "Local user"})
        if request.path == "/api/albums":
            return web.json_response([])
        if request.path == "/api/search/random":
            payload: dict[str, Any] = await request.json()
            assert payload == {"size": 1, "type": "IMAGE"}
            return web.json_response([{"id": ASSET_ID, "type": "IMAGE"}])
        if request.path == f"/api/assets/{ASSET_ID}/thumbnail":
            assert request.query == {"size": "preview"}
            return web.Response(body=b"jpeg-preview", content_type="image/jpeg")
        raise web.HTTPNotFound

    app = web.Application()
    app.router.add_route("*", "/api/{tail:.*}", respond)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()

    try:
        sockets = site._server.sockets  # type: ignore[union-attr]
        port = sockets[0].getsockname()[1]
        async with aiohttp.ClientSession() as session:
            client = ImmichApiClient(
                session,
                f"http://127.0.0.1:{port}",
                "local-private-key",
            )
            result = await client.async_validate()
    finally:
        await runner.cleanup()

    assert result.server_version == "3.0.1"
    assert result.user_id == USER_ID
    assert seen_paths[-1] == (f"/api/assets/{ASSET_ID}/thumbnail?size=preview")
