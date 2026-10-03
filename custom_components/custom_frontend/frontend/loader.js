// Panel element for every Custom Frontend page. This file is public and holds
// no page content: it fetches the page bundle through the authenticated view,
// imports it from a blob URL and mounts the custom element it default-exports.

const PAGES_URL = "/api/custom_frontend/pages";

class CustomFrontendPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    this._forward("hass", hass);
    this._load();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    this._forward("narrow", narrow);
  }

  set route(route) {
    this._route = route;
    this._forward("route", route);
  }

  set panel(panel) {
    this._panel = panel;
    this._forward("panel", panel);
    this._load();
  }

  _forward(name, value) {
    if (this._page) this._page[name] = value;
  }

  async _load() {
    if (this._loading || !this._hass || !this._panel) return;
    this._loading = true;
    const { slug, entry, version } = this._panel.config;
    const base = `${PAGES_URL}/${encodeURIComponent(slug)}/`;
    try {
      const tag = `custom-frontend-page-${slug.replace(/_/g, "-")}-${version}`;
      if (!customElements.get(tag)) {
        const response = await this._hass.fetchWithAuth(`${base}${entry}?v=${version}`);
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
        const source = await response.text();
        const url = URL.createObjectURL(new Blob([source], { type: "text/javascript" }));
        let module;
        try {
          module = await import(url);
        } finally {
          URL.revokeObjectURL(url);
        }
        if (typeof module.default !== "function") {
          throw new Error("the page module has no default-exported element class");
        }
        if (!customElements.get(tag)) customElements.define(tag, module.default);
      }
      const page = document.createElement(tag);
      // Signed URL for a file next to the entry, for <img src> and the like.
      page.assetUrl = async (path) => {
        const { path: signed } = await this._hass.callWS({
          type: "auth/sign_path",
          path: `${base}${path}`,
        });
        return signed;
      };
      page.hass = this._hass;
      page.narrow = this._narrow;
      page.route = this._route;
      page.panel = this._panel;
      this.replaceChildren(page);
      this._page = page;
    } catch (err) {
      const message = document.createElement("pre");
      message.style.cssText = "padding:16px;white-space:pre-wrap;color:var(--error-color,red)";
      message.textContent = `Custom Frontend: page "${slug}" failed to load: ${err.message}`;
      this.replaceChildren(message);
      console.error(err);
    }
  }
}

if (!customElements.get("custom-frontend-panel")) {
  customElements.define("custom-frontend-panel", CustomFrontendPanel);
}
