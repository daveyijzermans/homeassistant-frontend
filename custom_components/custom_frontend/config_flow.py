"""Config flow for Custom Frontend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_PAGES_DIR, DEFAULT_PAGES_DIR, DOMAIN


class CustomFrontendConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the directory that holds the pages."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            pages_dir = user_input[CONF_PAGES_DIR].rstrip("/") or "/"
            if await self.hass.async_add_executor_job(Path(pages_dir).is_dir):
                return self.async_create_entry(
                    title="Custom Frontend", data={CONF_PAGES_DIR: pages_dir}
                )
            errors[CONF_PAGES_DIR] = "not_a_directory"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_PAGES_DIR, default=DEFAULT_PAGES_DIR): str}
            ),
            errors=errors,
        )
