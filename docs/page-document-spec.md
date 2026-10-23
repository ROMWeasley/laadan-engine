# Specification: Typed Page Document & Agentic Action Listeners

**Status:** Specification Draft (v1.0 — Phase 0 Blueprint)  

---

## 1. Purpose

When language models generate raw HTML inside JSON strings, two problems happen immediately: broken quote escaping (`\"`) corrupts the JSON response, and unclosed or malicious tags break the DOM.

`laadan-engine` avoids raw HTML-in-JSON by having the model emit a **Typed Page Document (Component AST)**:
1. Structural layout, cards, inputs, tables, and action buttons are represented as typed JSON objects validated by **Pydantic v2 discriminated unions** (`Annotated[Union[...], Field(discriminator="type")]`).
2. Only `RichText` nodes carry inline HTML formatting, which is cleaned on the server by `nh3` (Rust `ammonia`).
3. Interactive triggers render declarative **Agentic Action Listeners** (`data-laadan-*`) handled by the ~4 KB `laadan-client.js` script.

---

## 2. Page Document Schema (JSON Schema v1)

Note that model-generated proposals are always classified as `"evidence": "we"` (`Evidence.CONJECTURAL`). The model cannot self-assign `"wi"` (`VERIFIED`); promotion to `"wi"` happens exclusively in the server's `PageCompiler`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PageDocument",
  "type": "object",
  "additionalProperties": false,
  "required": ["version", "evidence", "title", "layout", "components"],
  "properties": {
    "version": {
      "type": "string",
      "const": "1.0"
    },
    "evidence": {
      "type": "string",
      "const": "we",
      "description": "Model proposals are always typed as conjectural (@we)"
    },
    "title": {
      "type": "string",
      "maxLength": 128
    },
    "layout": {
      "type": "string",
      "enum": ["default-shell", "app-sidebar", "split-view", "minimal-card"]
    },
    "theme": {
      "$ref": "#/$defs/ThemeTokens"
    },
    "components": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/ComponentNode"
      }
    }
  },
  "$defs": {
    "ThemeTokens": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "primary": { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "surface": { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "background": { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "text": { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "radius": { "type": "string", "enum": ["none", "sm", "md", "lg", "full"] },
        "font": { "type": "string", "enum": ["sans", "mono", "serif"] }
      }
    },
    "ComponentNode": {
      "type": "object",
      "required": ["type", "props"],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-zA-Z0-9_-]{1,64}$",
          "description": "Optional DOM target ID (prefixed server-side with ldn-user-)"
        },
        "type": {
          "type": "string",
          "enum": [
            "Container",
            "Card",
            "Heading",
            "Text",
            "RichText",
            "Badge",
            "ActionTrigger",
            "TextInput",
            "SelectField",
            "Checkbox",
            "Asset",
            "Table"
          ]
        },
        "props": {
          "type": "object",
          "description": "Validated per component type via Pydantic discriminated union"
        },
        "children": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ComponentNode"
          }
        }
      }
    }
  }
}
```

---

## 3. Component Catalog

In code (`src/laadan/domain/`), each component below is a dedicated Pydantic model with `extra="forbid"`, forming a discriminated union on `type`:

| Component | Permitted `props` | Rendering & Safety Rules |
| :--- | :--- | :--- |
| **`Container`** | `class?: string`, `scope?: string` | Renders `<div>` or `<section>`. If `scope` is set, adds `data-laadan-scope` so child inputs can be collected together. `class` tokens are filtered against `DESIGN_TOKEN_ALLOWLIST`. |
| **`Card`** | `title?: string`, `subtitle?: string`, `class?: string` | Renders a themed surface container (`<article class="ldn-card">`) holding `children`. |
| **`Heading`** | `level: 1..6`, `text: string` | Renders `<h1>`–`<h6>`. Plain text, Jinja2 HTML-escaped. |
| **`Text`** | `content: string`, `variant?: "body" \| "muted" \| "mono"` | Renders `<p>` or `<span>`. Plain text, zero raw markup. |
| **`RichText`** | `html: string` | Cleaned via `nh3` (`ammonia`), allowing safe inline formatting (`strong`, `em`, `code`, `pre`, `ul`, `ol`, `li`, `blockquote`, `a`, `details`, `summary`). |
| **`Badge`** | `label: string`, `tone?: "neutral" \| "success" \| "warning" \| "accent"` | Compact status pill (`<span class="ldn-badge">`), HTML-escaped. |
| **`ActionTrigger`** | `action: "ui.toggle" \| "ui.switch_tab" \| "state.patch" \| "intent.mutate" \| "intent.query"`, `intent?: string`, `target: string`, `label: string`, `variant?: "primary" \| "secondary" \| "ghost"`, `payload?: object`, `include_selectors?: string[]` | Renders `<button type="button">` wired up with declarative `data-laadan-*` Agentic Action Listener attributes. |
| **`TextInput`** | `name: string`, `label: string`, `placeholder?: string`, `value?: string`, `required?: boolean` | Renders `<label>` + `<input type="text">`. `name` must match `^[a-z0-9_-]{1,64}$`. |
| **`SelectField`** | `name: string`, `label: string`, `options: {value: string, label: string}[]`, `selected?: string` | Renders a validated `<select>` dropdown. |
| **`Checkbox`** | `name: string`, `label: string`, `checked?: boolean` | Renders a boolean `<input type="checkbox">` toggle. |
| **`Asset`** | `id: string`, `alt: string`, `size?: "sm" \| "md" \| "lg"` | Symbolic asset reference (e.g., `"asset:avatar-ada"`). Resolved server-side against `/static/assets/` or replaced with a local fallback SVG. |
| **`Table`** | `headers: string[]`, `rows: string[][]` | Renders a semantic `<table>`. All cells are HTML-escaped text. |

---

## 4. Agentic Action Listeners (`data-laadan-*`) & Wire Protocol

### 4.1 Declarative Listener Markup
Instead of generating custom JavaScript event handlers (`onclick="sendMessage()"`), the `PageCompiler` turns `ActionTrigger` nodes into declarative **Agentic Action Listeners**:

```html
<div id="ldn-user-new-contact-box" data-laadan-scope="contact-form" class="ldn-card">
  <label for="ldn-input-handle">Username</label>
  <input id="ldn-input-handle" name="handle" type="text" value="@ada_lovelace" />

  <label for="ldn-input-bio">Note</label>
  <input id="ldn-input-bio" name="note" type="text" value="Met at Analytical Engine workshop" />

  <button
    type="button"
    data-laadan-action="intent.mutate"
    data-laadan-intent="save_contact"
    data-laadan-target="contact-list-pane"
    data-laadan-payload='{"source_app": "whatsapp", "entity_type": "contact"}'
    data-laadan-include="#ldn-user-active-channel"
    class="ldn-btn ldn-btn-primary">
    Add to Contacts
  </button>
</div>
```

### 4.2 Context Gathering in `laadan-client.js` (~4 KB Vanilla JS)
When a user clicks an element with `data-laadan-action`:
1. The listener intercepts the event (`event.preventDefault()`).
2. Reads static JSON parameters from `data-laadan-payload`.
3. Collects input values (`input`, `select`, `textarea`) from the nearest enclosing `[data-laadan-scope]` container or `<form>`.
4. Queries any extra DOM selectors listed in `data-laadan-include` inside a `try/catch` block and extracts their current `.value` or `.textContent`.
5. Sends a structured JSON `ActionEnvelope` to `POST /api/v1/action`.

### 4.3 Client-to-Server Request (`POST /api/v1/action`)
```json
{
  "protocol_version": "1.0",
  "route": "/whatsapp",
  "action": "intent.mutate",
  "intent": "save_contact",
  "target": "contact-list-pane",
  "payload": {
    "source_app": "whatsapp",
    "entity_type": "contact"
  },
  "form_values": {
    "handle": "@ada_lovelace",
    "note": "Met at Analytical Engine workshop"
  },
  "included_context": {
    "#ldn-user-active-channel": "general-chat"
  },
  "csrf_token": "token_cryptographic_nonce"
}
```

### 4.4 Server-to-Client Response (`ActionResponse`)
The server validates the envelope (`@wa`), updates the `CarrierBag` (storing `@ada_lovelace` in SQLite so the contact also appears on `/instagram`), compiles the updated component subtree (`@wi`), and returns `application/vnd.laadan.action-response+json`:

```json
{
  "protocol_version": "1.0",
  "evidence": "wi",
  "status": "ok",
  "mutations": [
    {
      "op": "MORPH_FRAGMENT",
      "target": "contact-list-pane",
      "html": "<div id=\"ldn-user-contact-list-pane\" class=\"ldn-stack\"><article class=\"ldn-card\"><strong>@ada_lovelace</strong><p class=\"ldn-muted\">Met at Analytical Engine workshop (synced to CarrierBag)</p></article></div>"
    }
  ],
  "sync": {
    "next_csrf_token": "token_next_nonce"
  }
}
```

### 4.5 Supported DOM Mutation Operations
`laadan-client.js` resolves `mutation.target` via `document.getElementById("ldn-user-" + mutation.target) || document.getElementById(mutation.target)` and applies one of five bounded DOM operations:
* **`MORPH_FRAGMENT`:** Morphs the existing DOM subtree in place, preserving scroll position and input focus.
* **`REPLACE_FRAGMENT`:** Replaces the target element's `outerHTML` with the server-compiled fragment.
* **`APPEND_FRAGMENT`:** Appends the compiled fragment as the last child of the target container (e.g., appending a new chat bubble).
* **`PREPEND_FRAGMENT`:** Prepends the compiled fragment as the first child of the target container (e.g., prepending a new feed post).
* **`REMOVE_ELEMENT`:** Removes the target element from the DOM.
