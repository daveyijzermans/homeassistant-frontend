"""Constants for Custom Frontend."""

from typing import Final

DOMAIN: Final = "custom_frontend"

CONF_PAGES_DIR: Final = "pages_dir"
DEFAULT_PAGES_DIR: Final = "/config/dashboards"

PAGE_MANIFEST: Final = "page.json"
PANEL_ELEMENT: Final = "custom-frontend-panel"
LOADER_URL: Final = f"/{DOMAIN}/loader.js"
PAGES_URL: Final = f"/api/{DOMAIN}/pages"
