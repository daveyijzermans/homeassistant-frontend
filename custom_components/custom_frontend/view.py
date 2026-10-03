"""Authenticated file view for page bundles and assets."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp import web

from homeassistant.components.http import KEY_HASS, KEY_HASS_USER, HomeAssistantView

from .const import DOMAIN, PAGES_URL
from .pages import resolve_file


class PageFileView(HomeAssistantView):
    """Serve files of registered pages to authenticated users only.

    The http auth middleware accepts a Bearer token or an `authSig` signed
    path; anything else never reaches the handler.
    """

    url = PAGES_URL + "/{slug}/{path:.+}"
    name = f"api:{DOMAIN}:pages"
    requires_auth = True

    async def get(self, request: web.Request, slug: str, path: str) -> web.StreamResponse:
        hass = request.app[KEY_HASS]
        page = hass.data.get(DOMAIN, {}).get("pages", {}).get(slug)
        if page is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        if page.require_admin and not request[KEY_HASS_USER].is_admin:
            return web.Response(status=HTTPStatus.FORBIDDEN)
        target = await hass.async_add_executor_job(resolve_file, page.directory, path)
        if target is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return web.FileResponse(target, headers={"Cache-Control": "no-cache"})
