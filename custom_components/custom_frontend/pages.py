"""Discovery of pages and safe resolution of their files."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path, PurePosixPath
import re

import voluptuous as vol

from .const import PAGE_MANIFEST

_LOGGER = logging.getLogger(__name__)

SLUG_RE = re.compile(r"^[a-z0-9_][a-z0-9_-]*$")
URL_PATH_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _relative_file(value: str) -> str:
    """Validate a path relative to the page directory."""
    if not is_safe_relative(value):
        raise vol.Invalid(f"unsafe path: {value}")
    return value


def _url_path(value: str) -> str:
    if not URL_PATH_RE.match(value):
        raise vol.Invalid(f"invalid url_path: {value}")
    return value


PAGE_SCHEMA = vol.Schema(
    {
        vol.Required("title"): str,
        vol.Optional("icon", default="mdi:view-dashboard"): str,
        vol.Optional("url_path"): _url_path,
        vol.Optional("require_admin", default=False): bool,
        vol.Optional("entry", default="page.js"): _relative_file,
    }
)


@dataclass(frozen=True)
class Page:
    """One page directory with a valid manifest."""

    slug: str
    directory: Path
    title: str
    icon: str
    url_path: str
    require_admin: bool
    entry: str
    version: str


def is_safe_relative(path: str) -> bool:
    """Return True for a plain relative path without dot segments."""
    parts = PurePosixPath(path).parts
    if not parts or PurePosixPath(path).is_absolute() or "\\" in path:
        return False
    return all(part and not part.startswith(".") for part in parts)


def resolve_file(directory: Path, path: str) -> Path | None:
    """Return the file `path` names inside `directory`, or None."""
    if not is_safe_relative(path):
        return None
    root = directory.resolve()
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def _version(file: Path) -> str:
    stat = file.stat()
    return hashlib.sha1(f"{stat.st_mtime_ns}:{stat.st_size}".encode()).hexdigest()[:10]


def scan_pages(root: Path) -> dict[str, Page]:
    """Read every `<root>/<slug>/page.json`; invalid pages are logged and skipped."""
    pages: dict[str, Page] = {}
    if not root.is_dir():
        _LOGGER.warning("Pages directory %s does not exist", root)
        return pages
    for directory in sorted(root.iterdir()):
        manifest = directory / PAGE_MANIFEST
        if directory.name.startswith(".") or not manifest.is_file():
            continue
        slug = directory.name
        if not SLUG_RE.match(slug):
            _LOGGER.error("Skipping page %s: invalid directory name", slug)
            continue
        try:
            conf = PAGE_SCHEMA(json.loads(manifest.read_text(encoding="utf-8")))
        except (ValueError, vol.Invalid) as err:
            _LOGGER.error("Skipping page %s: %s", slug, err)
            continue
        url_path = conf.get("url_path", slug)
        if not URL_PATH_RE.match(url_path):
            _LOGGER.error("Skipping page %s: set a url_path", slug)
            continue
        entry = resolve_file(directory, conf["entry"])
        if entry is None:
            _LOGGER.error("Skipping page %s: entry %s not found", slug, conf["entry"])
            continue
        pages[slug] = Page(
            slug=slug,
            directory=directory,
            title=conf["title"],
            icon=conf["icon"],
            url_path=url_path,
            require_admin=conf["require_admin"],
            entry=conf["entry"],
            version=_version(entry),
        )
    return pages
