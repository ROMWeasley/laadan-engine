# Security Model

**Status:** Design proposal. This document describes required behavior. Nothing is implemented yet.

---

## 1. Scope

The central question: **can model output make the server or the browser execute something, read something, or contact something it should not?** The design answers this with structural controls that do not depend on the model behaving well. Prompt injection is expected, not prevented (section 8).

### 1.1 Actors

| Actor | Trust in v1 | Notes |
| :--- | :--- | :--- |
| Local user | Trusted | Single user on loopback. Input is validated for shape and size, not for intent. See section 9. |
| Model | Untrusted, assumed adversarial | May hallucinate or follow instructions injected through user input or stored data. |
| Other websites in the same browser | Untrusted | May try to send requests to `127.0.0.1` (CSRF, DNS rebinding, cost abuse). |
| Model provider | Receives prompts | Sees everything in a prompt. Never receives secrets. |
| Repository files | Trusted | Templates, client script, stylesheet, assets, fixtures. Reviewed like code. |

### 1.2 Goals

* **G1.** No model output is executed as code: not on the server (Python, SQL, shell, templates, file paths) and not in the browser (JavaScript, event handlers, URL schemes, CSS).
* **G2.** Model output cannot make the browser contact any origin other than the engine's own.
* **G3.** Model output cannot read or change files, configuration, or secrets, and cannot make the server send requests anywhere except the configured model endpoint.
* **G4.** Resource use caused by model output or by requests is bounded (size, depth, count, time, rate).
* **G5.** Other websites cannot make the engine generate pages, run actions, or read responses.

### 1.3 Non-goals in v1

* Protecting the local user from their own input.
* Truthfulness of generated content.
* Isolation between multiple users.
* Preventing prompt injection.
* Preventing misleading generated content (section 9).

---

## 2. Where Model Output Could Do Harm

### 2.1 In the browser

| Sink | Example | Control |
| :--- | :--- | :--- |
| Script elements, event handlers | `<script>`, `<img onerror=...>` | Templates never insert model strings as markup. `RichText` passes through nh3, which removes scripts and all `on*` attributes. Output check. CSP. |
| URL attributes | `javascript:alert(1)`, `//evil.tld` | `Link` targets and `RichText` `href` values must match the internal route pattern. Images come only from the asset catalog. No external links in v1. |
| CSS | `<style>`, `style="..."`, `url()` beacons, full-screen overlays | No style elements or attributes from the model. Themes are validated tokens compiled into a server-generated stylesheet. CSP `style-src 'self'`. |
| Attribute breakout | Text value `" onmouseover="...` | Jinja2 autoescaping. All template attributes are quoted. Attribute names are fixed in templates. |
| DOM clobbering | `id="ldn-app"`, `name="getElementById"` | Model IDs are rendered with the prefix `u-`; server IDs use `ldn-`. The client uses `getElementById` with the prefix and never reads named properties of `window`, `document`, or forms. |
| Unintended actions | A button that triggers a server operation it should not | Buttons carry only a server-assigned ID. Action kinds come from a fixed enum. The model cannot reference engine-internal actions. |
| Data exfiltration | Image beacons, `fetch`, form posts to other hosts | CSP limits `img-src`, `connect-src`, and `form-action` to `'self'`. No external URLs in generated markup. |
| Misuse of the client script | Model data that the client interprets as code | The client never evaluates anything. It inserts HTML only from the engine's own JSON responses, through a Trusted Types policy where the browser supports it. |

### 2.2 On the server

| Sink | Example | Control |
| :--- | :--- | :--- |
| Code execution | `eval`, `exec`, `pickle`, `yaml.load`, subprocess | Model output is parsed only as JSON into Pydantic models. None of these functions are used anywhere in the codebase. |
| Template injection | Model text containing `{{ ... }}` | Templates are loaded only from the package directory. Model strings are passed as variables, never as template source. |
| SQL injection | Entity type `contact'; DROP TABLE ...` | Parameterized queries on a fixed schema. Entity types and attribute names are values, never identifiers. |
| Path traversal | Asset ID `../../.env` | Asset IDs are looked up in the catalog dictionary. Route paths and model strings are never used to build file paths. |
| SSRF | Model asks the server to fetch a URL | The server never fetches URLs from model output or requests. The only outbound connection is the configured model endpoint. |
| Resource exhaustion | 10,000 nested nodes, 50 MB response | Limits in section 7, checked before and during parsing. |
| Secret leakage | Model asks for the API key | Secrets are never placed in prompts, rendered pages, or logs. Error responses are generic. |
| Memory poisoning | Model deletes or rewrites all contacts | Entity operations are typed and capped per response. Entities written by the model are marked `we`. The worst case is wrong data, not code execution. |

---

## 3. The Compiler Pipeline

Every response that contains model-derived content passes these stages in order. A failure at any stage produces the fallback (section 3.7).

```text
raw model text (we)
   │
   ▼
1. Parse      JSON only, size checked before parsing
   │
   ▼
2. Validate   Pydantic v2, strict mode, extra fields forbidden, limits from section 7
   │
   ▼
3. Resolve    asset IDs exist in the catalog, targets exist in the stored page, IDs unique
   │
   ▼
4. Render     application-owned Jinja2 templates, autoescaping on
   │
   ▼
5. Sanitize   RichText only, through nh3 with the allowlist in 3.2
   │
   ▼
6. Verify     final HTML parsed with selectolax and checked against 3.3
   │
   ▼
7. Deliver    security headers from 3.5
```

### 3.1 Rendering

* Each component type has exactly one template. Templates are part of the repository.
* Model strings appear in templates in only three ways:
  * as **text content**, escaped by Jinja2;
  * as **attribute values** that have already passed an enum or regex check (IDs, input names, variants, theme tokens);
  * as **sanitized `RichText`** inside a type called `SafeHtml`.
* `SafeHtml` can only be constructed by the sanitizer. It is the only type the templates output without escaping. Code review and a test assert that no other code marks strings as safe (`Markup(...)`, the `|safe` filter).
* Model strings have control characters and bidirectional override characters removed before rendering.

### 3.2 `RichText` sanitizer configuration (nh3)

nh3 is a Python binding for the Rust library ammonia. It parses HTML with html5ever, an HTML5-compliant parser, keeps only allowlisted tags and attributes, and serializes a new, well-formed fragment.

| Setting | Value |
| :--- | :--- |
| Tags | `p`, `br`, `strong`, `em`, `code`, `pre`, `blockquote`, `ul`, `ol`, `li`, `a`, `details`, `summary`, `del`, `sub`, `sup`, `hr` |
| Attributes | `href` on `a`. No other attributes on any tag (no `id`, `class`, `style`, `name`). |
| `href` filter | Kept only if the value matches the internal route pattern (starts with a single `/`, no scheme, no `//`). Otherwise removed. |
| Removed with content | `script`, `style` |
| Comments | Removed |

The tag list contains no elements that switch the parser into a different mode (`svg`, `math`, `template`, `textarea`, `title`, `noscript`, `style`, `xmp`). Such elements are a common source of mutation XSS, where markup changes meaning when it is parsed a second time.

`<details>` and `<summary>` give the model expandable sections that work in the browser without any script.

### 3.3 Output check (selectolax)

selectolax is a Python binding for lexbor, a fast HTML5 parser. The rendered page or fragment is parsed again and checked:

* `script` elements: only the shell's `<script src="/static/laadan-client.js">`.
* No `style` elements and no `style` attributes.
* No attributes whose name starts with `on`.
* No `iframe`, `object`, `embed`, `form`, `base`, `meta`, or `link` inside the app root. The shell contains exactly the expected `meta` and `link` elements.
* Every `href` inside the app root matches the internal route pattern. Every `src` starts with `/static/`.
* Every `id` inside the app root starts with `u-`.
* `data-laadan-*` attributes come only from the set in the protocol spec, and their values match its patterns.

This is a second, independent check. It cannot prove that every browser parses the HTML the same way, which is why the CSP exists as a third layer.

### 3.4 Themes

* The model may set theme tokens for an app: colors as `#rrggbb`, and enums for radius, font, and density.
* The server writes them into `/_laadan/theme/{app}.css` as CSS custom properties (`--ldn-primary: #10b981;`).
* Values cannot contain `;`, `{`, `}`, `(`, quotes, or `url`, because they must match the regex or enum exactly.
* The stylesheet is generated only from stored, validated tokens. The model never supplies CSS text, selectors, or class names.

### 3.5 Response headers

Every HTML response carries:

```http
Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; require-trusted-types-for 'script'; trusted-types laadan
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
```

* No inline scripts or inline styles are needed, so neither `'unsafe-inline'` nor nonces are required. Even if markup slipped through every earlier stage, the browser would not run an inline script or apply an inline style.
* `require-trusted-types-for 'script'` makes the browser reject HTML insertion through `innerHTML` and similar APIs unless the value comes from the client's named policy `laadan`. Browsers without Trusted Types support ignore this directive; the other controls still apply.
* The CSP is always sent. It is not configurable.
* JSON responses carry `Content-Type: application/json` and `X-Content-Type-Options: nosniff`.

### 3.6 Client script rules

The client script (`laadan-client.js`) is part of the security core and is reviewed by hand. It has no dependencies and no build step.

* No `eval`, `Function`, string arguments to `setTimeout` or `setInterval`, or dynamic `import`.
* `fetch` only to `/_laadan/action` on the same origin, with a JSON body.
* HTML is inserted only from responses of that endpoint, through the Trusted Types policy `laadan`.
* Targets are resolved with `document.getElementById("u-" + target)` and must be inside the app root (`#ldn-app`). Anything else is ignored.
* The only navigation it performs is `location.reload()` for the `reload` operation.
* Payloads and action definitions are never read from the page. The page contains only action IDs.

### 3.7 GlitchBoundary (fallback)

When parsing, validation, resolution, rendering, sanitizing, or verification fails:

* No part of the rejected output is sent to the browser.
* Full pages are replaced by a static fallback page with a retry button. Action responses contain one `replace` operation with a static fallback fragment.
* The rejected output and the error are written to the local log for debugging.
* No stack traces or internal details are sent to the client.

---

## 4. Actions

Actions follow an application-owned allowlist:

* The model can create buttons with two kinds of action: `toggle` (UI-only) and `intent` (generative). Tab switching is generated by the server for `Tabs` components. Engine actions such as `shell.regenerate` exist only in server templates.
* When a page is stored, the server assigns each button an action ID and stores its definition: kind, target, intent label, payload, and include list.
* The rendered button carries only `data-laadan-action="a12"`. Model-supplied payloads stay on the server.
* An action request is accepted only if the action ID exists on the stored page for that route, the submitted value names match the inputs in the button's scope, and the included element IDs match the stored include list.
* An `intent` label is a short snake_case string that describes the action to the model. It grants no capability; the server does not map it to code.

---

## 5. Entity Store

* One table of entities: server-assigned ID, type, attributes as JSON, source route, evidential, timestamps.
* The model can propose `create`, `update`, and `delete` operations. At most 20 operations per response.
* Entity types match `^[a-z][a-z0-9_]{0,31}$`. Attributes are a flat JSON object with at most 32 keys and 4 KB in total. Values are strings, numbers, booleans, null, or lists of these.
* All queries are parameterized. Types and attribute names are stored as values.
* Entities written by the model are marked `we`, even when the content came from user input. Per-field provenance is later work.

---

## 6. Requests From Other Websites

Treating the local user as trusted does not make other websites trusted. A page open in another tab can send requests to `127.0.0.1`. These controls address that:

| Control | Protects against |
| :--- | :--- |
| `Host` header must be in `LAADAN_ALLOWED_HOSTS` | DNS rebinding: a foreign domain that resolves to `127.0.0.1` would otherwise count as same-origin. |
| `POST` requests and JSON-mode requests from browsers require `Origin` to match, or `Sec-Fetch-Site: same-origin` | Cross-site request forgery |
| Request bodies must be `application/json` | Cross-site pages cannot send JSON without a CORS preflight, and the server allows no CORS. |
| No CORS headers | Other origins cannot read responses. |
| Cross-site navigations to ungenerated routes get a confirmation page | Cost abuse through links or redirects |
| Cross-site subresource requests and prefetches never generate | Cost abuse through `<img src>`, `fetch`, or browser prefetching |
| No cookies in v1 | There is no session that could be stolen or ridden. |

Non-browser clients such as `curl` and Postman send no `Origin` or `Sec-Fetch-*` headers and are allowed. They are not a cross-site risk.

---

## 7. Limits

Limits are constants in the `domain` package, not configuration.

| Item | Limit |
| :--- | :--- |
| Request body | 64 KB |
| Raw model response | 256 KB |
| Nodes per page document | 500 |
| Tree depth | 12 |
| Plain text field | 2,000 characters |
| `RichText` field | 8,000 characters |
| Table | 50 rows × 10 columns |
| Buttons per page | 100 |
| Entity operations per response | 20 |
| `need_assets` rounds per generation | 1 |
| JSON-mode response body | 64 KB, depth 8 |
| Stored pages | 500, least recently used evicted |

Size limits are checked before parsing, so an oversized response is rejected without being parsed. Regular expressions run only on length-checked strings.

---

## 8. Prompt Injection

Prompt injection cannot be prevented at the prompt level. User input, stored entities, and earlier model output all end up in prompts and can contain instructions.

With the controls above, a successful injection can cause:

* misleading or wrong content in generated pages,
* wrong entity data, marked `we`,
* wasted model calls, bounded by the rate limiter.

It cannot cause code execution in the server or browser, requests to other origins, or access to files, configuration, or secrets, because none of these are reachable from validated model output.

Data sections in prompts are JSON-encoded, delimited, and labeled with their evidential. This reduces confusion between instructions and data; it is not relied on for security.

---

## 9. Residual Risks and Later Work

### 9.1 Residual risks in v1

* **Misleading content.** The model can build a page that looks like a login form or asks for sensitive data. Values entered there go only to the engine and the model provider. The server-owned shell marks the generated area.
* **The model provider sees all prompt content.** Anything typed into a generated page is sent to the provider in `direct` and `batched` mode.
* **Local access.** Any process or user on the same machine can reach the loopback port.
* **Browser differences.** Trusted Types is not supported in every browser. CSP and the output check still apply there.
* **Dependency correctness.** The design relies on Jinja2, nh3 and ammonia, selectolax and lexbor, Pydantic, and the browser's CSP enforcement. A lock file will be added with the first runtime code.

### 9.2 Later work for multi-user operation

* Sessions with `HttpOnly`, `SameSite=Strict` cookies and authentication.
* Per-user entity and page stores, per-user rate limits.
* Content from other users treated as untrusted input. It is already escaped and sanitized like model output.
* External links through a confirmation page with an allowlist.
* Per-field provenance, so values copied from user input can stay `wa`.

---

## 10. Testing Strategy

* **Hostile fixtures.** `MockModelGateway` ships fixtures that simulate malicious model output. Each must end in either safe HTML or the fallback:
  * `<script>` in a `Text` field, an `onerror` attribute in `RichText`
  * `javascript:`, `data:`, and `//evil.tld` links
  * `style` attributes, `<svg>` and `<math>` content, nested `<template>`
  * a 10,000-level tree, a 1 MB response, truncated JSON
  * unknown component types, extra fields, a self-assigned evidential
  * targets that point at shell IDs or nonexistent IDs
  * oversized or malformed entity operations
* **Output-check tests.** Rendered fixtures are checked with the rules from section 3.3.
* **Header tests.** Every response type carries the headers from section 3.5.
* **Origin tests.** Requests with foreign `Host`, cross-site `Origin`, `text/plain` bodies, and prefetch headers are rejected or answered without generation.
* **Static checks.** Ruff with the bandit rules (`S`) flags `eval`, `exec`, `pickle`, `subprocess`, and similar calls in the codebase.
