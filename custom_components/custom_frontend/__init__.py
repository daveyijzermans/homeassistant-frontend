"""Custom Frontend: authored pages as authenticated sidebar panels."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PAGES_DIR, DOMAIN, LOADER_URL, PANEL_ELEMENT
from .pages import Page, scan_pages
from .view import PageFileView

_LOGGER = logging.getLogger(__name__)

LOADER_FILE = Path(__file__).parent / "frontend" / "loader.js"


def _file_hash(file: Path) -> str:
    return hashlib.sha1(file.read_bytes()).hexdigest()[:10]


async def _async_register_http(hass: HomeAssistant, data: dict) -> None:
    """Routes cannot be removed from aiohttp, so they register once per run."""
    if "loader_version" in data:
        return
    await hass.http.async_register_static_paths(
        [StaticPathConfig(LOADER_URL, str(LOADER_FILE), False)]
    )
    hass.http.register_view(PageFileView())
    data["loader_version"] = await hass.async_add_executor_job(_file_hash, LOADER_FILE)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.setdefault(DOMAIN, {})
    await _async_register_http(hass, data)

    found = await hass.async_add_executor_job(
        scan_pages, Path(entry.data[CONF_PAGES_DIR])
    )
    pages: dict[str, Page] = {}
    for page in found.values():
        try:
            await panel_custom.async_register_panel(
                hass,
                frontend_url_path=page.url_path,
                webcomponent_name=PANEL_ELEMENT,
                sidebar_title=page.title,
                sidebar_icon=page.icon,
                module_url=f"{LOADER_URL}?v={data['loader_version']}",
                config={"slug": page.slug, "entry": page.entry, "version": page.version},
                require_admin=page.require_admin,
            )
        except ValueError as err:
            _LOGGER.error("Skipping page %s: %s", page.slug, err)
            continue
        pages[page.slug] = page
    data["pages"] = pages
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.get(DOMAIN, {})
    for page in data.pop("pages", {}).values():
        frontend.async_remove_panel(hass, page.url_path, warn_if_unknown=False)
    return True
