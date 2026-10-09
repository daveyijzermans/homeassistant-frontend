// Panel element for every Custom Frontend page. This file is public and holds
// no page content: it fetches the page bundle through the authenticated view,
// imports it from a blob URL and mounts the custom element it default-exports.
//
// An open page follows rebuilds: whenever the panel becomes visible again, and
// every few minutes while it is visible, the loader asks for the bundle with
// the ETag it last loaded. An unchanged bundle answers 304; a changed one is
// imported under a new tag and replaces the page in place.

const PAGES_URL = "/api/custom_frontend/pages";
const RECHECK_MS = 5 * 60 * 1000;

let defined = 0;
// slug -> { etag, tag }: the newest build of each page this document defined, so a panel created again
// (navigating back) reuses it after a 304.
const builds = new Map();

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

  connectedCallback() {
    this._onVisible = () => document.visibilityState === "visible" && this._recheck();
    document.addEventListener("visibilitychange", this._onVisible);
    this._timer = setInterval(() => document.visibilityState === "visible" && this._recheck(), RECHECK_MS);
  }

  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._onVisible);
    clearInterval(this._timer);
  }

  _forward(name, value) {
    if (this._page) this._page[name] = value;
  }

  _url() {
    const { slug, entry, version } = this._panel.config;
    return `${PAGES_URL}/${encodeURIComponent(slug)}/${entry}?v=${version}`;
  }

  async _load() {
    if (this._loading || !this._hass || !this._panel) return;
    this._loading = true;
    try {
      const known = builds.get(this._panel.config.slug);
      const response = await this._hass.fetchWithAuth(this._url(), {
        headers: known?.etag ? { "If-None-Match": known.etag } : {},
        cache: "no-store",
      });
      if (response.status === 304 && known) this._show(known.tag, known.etag);
      else if (response.ok) await this._mount(response);
      else throw new Error(`${response.status} ${response.statusText}`);
    } catch (err) {
      this._fail(err);
    }
  }

  async _recheck() {
    if (!this._page || !this._etag || this._checking) return;
    this._checking = true;
    try {
      const response = await this._hass.fetchWithAuth(this._url(), {
        headers: { "If-None-Match": this._etag },
        cache: "no-store",
      });
      if (response.status === 200) await this._mount(response);
    } catch (err) {
      // The page stays as it is; the next check tries again.
      console.warn("Custom Frontend: checking for a new build failed", err);
    } finally {
      this._checking = false;
    }
  }

  async _mount(response) {
    const { slug } = this._panel.config;
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
    // A tag is defined once per document; every build gets its own.
    const tag = `custom-frontend-page-${slug.replace(/_/g, "-")}-${++defined}`;
    customElements.define(tag, module.default);
    const etag = response.headers.get("ETag");
    builds.set(slug, { etag, tag });
    this._show(tag, etag);
  }

  _show(tag, etag) {
    const { slug } = this._panel.config;
    const base = `${PAGES_URL}/${encodeURIComponent(slug)}/`;
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
    this._etag = etag;
  }

  _fail(err) {
    const { slug } = this._panel.config;
    const message = document.createElement("pre");
    message.style.cssText = "padding:16px;white-space:pre-wrap;color:var(--error-color,red)";
    message.textContent = `Custom Frontend: page "${slug}" failed to load: ${err.message}`;
    this.replaceChildren(message);
    console.error(err);
  }
}

if (!customElements.get("custom-frontend-panel")) {
  customElements.define("custom-frontend-panel", CustomFrontendPanel);
}
