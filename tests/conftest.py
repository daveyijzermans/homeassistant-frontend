"""Fixtures for Custom Frontend tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.custom_frontend.const import CONF_PAGES_DIR, DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components from this repo."""


def write_page(root: Path, slug: str, manifest: dict, files: dict[str, str]) -> Path:
    directory = root / slug
    directory.mkdir(parents=True)
    (directory / "page.json").write_text(json.dumps(manifest))
    for name, content in files.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return directory


@pytest.fixture
def pages_dir(tmp_path: Path) -> Path:
    root = tmp_path / "pages"
    root.mkdir()
    write_page(root, "home", {"title": "Home"}, {"page.js": "export default class {}"})
    write_page(
        root,
        "_admin",
        {"title": "Admin", "url_path": "admin-page", "require_admin": True},
        {"page.js": "export default class {}"},
    )
    (tmp_path / "secret.txt").write_text("outside")
    return root


async def setup_entry(hass: HomeAssistant, pages_dir: Path) -> MockConfigEntry:
    # The frontend needs the built frontend package; the panel registry it
    # owns works without it.
    hass.config.components.add("frontend")
    hass.config.components.add("panel_custom")
    assert await async_setup_component(hass, "http", {})
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PAGES_DIR: str(pages_dir)})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def entry(hass: HomeAssistant, pages_dir: Path) -> MockConfigEntry:
    return await setup_entry(hass, pages_dir)
