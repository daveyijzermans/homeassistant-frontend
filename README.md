# Custom Frontend

Home Assistant integration that turns hand-authored pages into sidebar panels. A page is plain HTML/JS or the output of any framework build, and only logged-in users can fetch it; files under `/local` are public, these are not.

## How it works

- Each page is a folder in the pages directory with a `page.json`. Every page becomes a panel at `/<url_path>`.
- All panels use one small public loader script. The loader fetches the page bundle from `/api/custom_frontend/pages/<slug>/<entry>` with the user's token, imports it and mounts it.
- An open page follows rebuilds: when the panel becomes visible again, and every five minutes while it is visible, the loader asks for the bundle with the ETag it loaded, and swaps in the new build when it changed. No reload or app restart is needed.
- That API accepts only a Bearer token or a signed URL, serves only files inside the page's folder and skips dotfiles. Admin-only pages refuse other users.

## Install

Add this repository to HACS as a custom integration, install it, then add the **Custom Frontend** integration and point it at the pages directory (default `/config/dashboards`). Keep that directory outside `/config/www`.

After adding, changing or removing a page, reload the integration. Open browsers then load the new bundle on their next visit to the panel.

## page.json

```json
{
  "title": "Energy",
  "icon": "mdi:flash",
  "url_path": "energy-live",
  "require_admin": false,
  "entry": "dist/page.js"
}
```

- `title`: sidebar title, required.
- `icon`: sidebar icon, default `mdi:view-dashboard`.
- `url_path`: panel path, default the folder name. A path another panel or dashboard already uses is skipped with an error in the log.
- `require_admin`: hide the panel from non-admins and refuse them its files, default `false`.
- `entry`: the bundle relative to the folder, default `page.js`.

Folder names are lowercase letters, digits, `_` and `-`.

## The page contract

The entry is a single ES module whose default export is a custom element class. Do not register the element yourself; the loader picks the tag name.

The loader sets the same properties Home Assistant gives any panel, and updates them when they change:

- `hass`: state, services, `callWS`, `fetchWithAuth`.
- `narrow`, `route`, `panel`.

It also sets `assetUrl(path)`, which resolves to a short-lived signed URL for a file next to the entry, for `<img src>` and other places that cannot send a token.

The bundle is imported from a blob URL, so relative `import` statements do not resolve. Bundle everything into one file, for example Vite in library mode with `formats: ["es"]` and `inlineDynamicImports`, and either inline assets or load them through `assetUrl`.

```js
export default class HelloPage extends HTMLElement {
  set hass(hass) {
    this.textContent = `Hello ${hass.user.name}`;
  }
}
```

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install pytest-homeassistant-custom-component
.venv/bin/pytest
```
