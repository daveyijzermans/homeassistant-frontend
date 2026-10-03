"""Tests for serving and registering Custom Frontend pages."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import shutil

from homeassistant.components.frontend import DATA_PANELS
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant

from custom_components.custom_frontend.const import LOADER_URL, PAGES_URL

from custom_components.custom_frontend.pages import scan_pages

from .conftest import setup_entry, write_page

HOME_JS = f"{PAGES_URL}/home/page.js"


async def test_unauthenticated_is_rejected(hass: HomeAssistant, entry, hass_client_no_auth) -> None:
    client = await hass_client_no_auth()
    assert (await client.get(HOME_JS)).status == 401


async def test_bearer_token_is_served(hass: HomeAssistant, entry, hass_client) -> None:
    client = await hass_client()
    response = await client.get(HOME_JS)
    assert response.status == 200
    assert await response.text() == "export default class {}"
    assert response.headers["Cache-Control"] == "no-cache"


async def test_signed_path_is_served(
    hass: HomeAssistant, entry, hass_client_no_auth, hass_access_token
) -> None:
    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    signed = async_sign_path(hass, HOME_JS, timedelta(seconds=30), refresh_token_id=refresh_token.id)
    client = await hass_client_no_auth()
    assert (await client.get(signed)).status == 200
    other = signed.replace("/home/page.js", "/_admin/page.js")
    assert (await client.get(other)).status == 401


async def test_loader_is_public(hass: HomeAssistant, entry, hass_client_no_auth) -> None:
    client = await hass_client_no_auth()
    response = await client.get(LOADER_URL)
    assert response.status == 200
    assert "custom-frontend-panel" in await response.text()


async def test_paths_cannot_escape_the_page(
    hass: HomeAssistant, entry, hass_client, pages_dir: Path
) -> None:
    (pages_dir / "home" / ".hidden").write_text("hidden")
    (pages_dir / "home" / "link.txt").symlink_to(pages_dir.parent / "secret.txt")
    client = await hass_client()
    for path in (
        "home/%2e%2e/%2e%2e/secret.txt",
        "home/..%2f..%2fsecret.txt",
        "home/.hidden",
        "home/link.txt",
        "home/page.json/x",
        "missing/page.js",
    ):
        response = await client.get(f"{PAGES_URL}/{path}")
        assert response.status in (400, 404), path
        assert await response.text() != "outside"


async def test_admin_page_needs_admin(
    hass: HomeAssistant, entry, hass_client, hass_read_only_access_token
) -> None:
    user_client = await hass_client(hass_read_only_access_token)
    assert (await user_client.get(f"{PAGES_URL}/_admin/page.js")).status == 403
    assert (await user_client.get(HOME_JS)).status == 200
    admin_client = await hass_client()
    assert (await admin_client.get(f"{PAGES_URL}/_admin/page.js")).status == 200


async def test_panels_register_and_unregister(hass: HomeAssistant, entry, pages_dir: Path) -> None:
    panels = hass.data[DATA_PANELS]
    home = panels["home"]
    assert home.component_name == "custom"
    assert home.sidebar_title == "Home"
    assert home.config["slug"] == "home"
    assert home.config["_panel_custom"]["name"] == "custom-frontend-panel"
    assert home.config["_panel_custom"]["module_url"].startswith(LOADER_URL)
    assert panels["admin-page"].require_admin is True

    shutil.rmtree(pages_dir / "home")
    write_page(pages_dir, "added", {"title": "Added"}, {"page.js": "export default class {}"})
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert "home" not in panels
    assert "added" in panels

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert "added" not in panels
    assert "admin-page" not in panels


async def test_invalid_pages_are_skipped(hass: HomeAssistant, pages_dir: Path) -> None:
    write_page(pages_dir, "noentry", {"title": "No entry"}, {})
    write_page(pages_dir, "badentry", {"title": "Bad", "entry": "../home/page.js"}, {})
    write_page(pages_dir, "Upper", {"title": "Upper"}, {"page.js": ""})
    write_page(pages_dir, "notitle", {}, {"page.js": ""})
    write_page(pages_dir, "clash", {"title": "Clash", "url_path": "home"}, {"page.js": ""})
    (pages_dir / "broken").mkdir()
    (pages_dir / "broken" / "page.json").write_text("{")

    pages = await hass.async_add_executor_job(scan_pages, pages_dir)
    assert set(pages) == {"home", "_admin", "clash"}

    # "clash" and "home" share a url_path; pages register in name order,
    # so "clash" holds it and "home" is skipped.
    await setup_entry(hass, pages_dir)
    assert hass.data[DATA_PANELS]["home"].config["slug"] == "clash"
    assert set(hass.data["custom_frontend"]["pages"]) == {"_admin", "clash"}
