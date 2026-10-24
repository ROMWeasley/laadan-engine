# Page Document and Action Protocol

**Status:** Draft 0.1. Once implemented, the Pydantic models in `src/laadan/domain/` are the source of truth, and the JSON Schema sent to the model is generated from them. This document describes intent and examples, not a frozen format.

---

## 1. Model Response Types

The model always answers with one JSON object. The field `kind` selects the type:

| `kind` | Used for | Content |
| :--- | :--- | :--- |
| `page` | `GET` of a generated route | `title`, optional `theme`, `body` (component nodes), `entity_ops` |
| `update` | `intent` actions | `updates` (DOM operations with component nodes), `entity_ops` |
| `api` | JSON-mode requests | `status`, `body` (plain JSON), `entity_ops` |
| `need_assets` | Asking for asset entries, at most once per generation | `categories` (up to 5 names) |

The model does not set evidentials. The server marks all model output as `we`. Unknown fields fail validation, including any attempt to declare an evidential.

---

## 2. Components

All components are flat JSON objects with a `type` field, validated as a Pydantic discriminated union with `extra="forbid"`.

Common optional fields:

* `id`: pattern `^[a-z][a-z0-9-]{0,31}$`, unique per page. Rendered as `id="u-<id>"`. Needed only for action targets and includes.
* `hidden`: boolean. Toggled by `toggle` actions.

| Type | Fields | Renders as |
| :--- | :--- | :--- |
| `Section` | `layout`: `stack` \| `row` \| `grid-2` \| `grid-3`, `gap`: `sm` \| `md` \| `lg`, `scope?`: boolean, `children` | `<section>` with layout classes; `data-laadan-scope` if `scope` is true |
| `Card` | `title?`, `subtitle?`, `children` | `<article class="ldn-card">` |
| `Heading` | `level`: 1–4, `text` | `<h1>` to `<h4>` |
| `Text` | `text`, `variant?`: `body` \| `muted` \| `mono` | `<p>` |
| `RichText` | `html` | Fragment sanitized by nh3 (see security model, section 3.2) |
| `Badge` | `label`, `tone?`: `neutral` \| `success` \| `warning` \| `accent` | `<span class="ldn-badge">` |
| `Link` | `label`, `to`: internal route | `<a href="/...">` |
| `Button` | `label`, `action`: `toggle` \| `intent`, `target`, `intent?`, `payload?`, `include?`, `variant?`: `primary` \| `secondary` \| `ghost` | `<button type="button" data-laadan-action="...">` |
| `TextInput` | `name`, `label`, `placeholder?`, `value?`, `multiline?` | `<label>` around `<input type="text">` or `<textarea>` |
| `Select` | `name`, `label`, `options`: list of `{value, label}` (max 50), `selected?` | `<label>` around `<select>` |
| `Checkbox` | `name`, `label`, `checked?` | `<label>` around `<input type="checkbox">` |
| `Disclosure` | `summary`, `open?`, `children` | `<details>` and `<summary>`, works without script |
| `Tabs` | `items`: list of `{label, children}` (max 8) | Tab bar with server-generated UI-only buttons |
| `Image` | `asset`: `^asset:[a-z0-9-]{1,64}$`, `alt`, `size?`: `sm` \| `md` \| `lg` | `<img>` with `src`, `width`, and `height` from the asset catalog; unknown IDs use a local placeholder |
| `Table` | `headers` (max 10), `rows` (max 50 × 10, strings) | `<table>`, all cells escaped |

Field patterns:

| Field | Rule |
| :--- | :--- |
| `name` (inputs) | `^[a-z][a-z0-9_]{0,31}$` |
| `to` (links) | Internal route pattern (see architecture, section 3) |
| `target`, `include` entries | Existing `id` on the same page; `include` has at most 10 entries |
| `intent` | `^[a-z][a-z0-9_]{0,63}$`, required when `action` is `intent` |
| `payload` | JSON object, at most 2 KB and depth 3; stored on the server only |
| Text fields | At most 2,000 characters; control and bidirectional override characters removed |

---

## 3. Theme Tokens

Optional `theme` object on a `page` response. It applies to the whole app (first route segment).

| Token | Rule |
| :--- | :--- |
| `primary`, `accent`, `background`, `surface`, `text` | `^#[0-9a-fA-F]{6}$` |
| `radius` | `none` \| `sm` \| `md` \| `lg` \| `full` |
| `font` | `sans` \| `serif` \| `mono` |
| `density` | `compact` \| `comfortable` |

The server writes validated tokens to `/_laadan/theme/{app}.css` as CSS custom properties.

---

## 4. Entity Operations

```json
[
  { "op": "create", "type": "contact", "attributes": { "name": "Ada Lovelace", "note": "Met at the workshop" } },
  { "op": "update", "id": "e_42", "attributes": { "note": "Prefers email" } },
  { "op": "delete", "id": "e_17" }
]
```

* IDs are assigned by the server. The model sees existing IDs in the memory section of the prompt.
* At most 20 operations per response. Limits on types and attributes: security model, section 5.

---

## 5. Example: Page Proposal

Model response for `GET /whatsapp`:

```json
{
  "kind": "page",
  "title": "Chats",
  "theme": { "primary": "#128c7e", "accent": "#25d366", "background": "#0b141a", "surface": "#111b21", "text": "#e9edef", "radius": "lg", "font": "sans", "density": "comfortable" },
  "body": [
    {
      "type": "Section", "layout": "row", "gap": "md",
      "children": [
        {
          "type": "Card", "title": "Contacts",
          "children": [
            {
              "type": "Section", "id": "contact-list", "layout": "stack", "gap": "sm",
              "children": [
                { "type": "Text", "id": "empty-hint", "text": "No contacts yet.", "variant": "muted" }
              ]
            }
          ]
        },
        {
          "type": "Card", "title": "New contact",
          "children": [
            {
              "type": "Section", "layout": "stack", "gap": "sm", "scope": true,
              "children": [
                { "type": "TextInput", "name": "name", "label": "Name" },
                { "type": "TextInput", "name": "note", "label": "Note", "multiline": true },
                {
                  "type": "Button", "label": "Add contact", "variant": "primary",
                  "action": "intent", "intent": "add_contact", "target": "contact-list",
                  "payload": { "entity_type": "contact" }
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "entity_ops": []
}
```

Rendered markup (excerpt):

```html
<main id="ldn-app" data-laadan-route="/whatsapp">
  <section id="u-contact-list" class="ldn-stack ldn-gap-sm">
    <p id="u-empty-hint" class="ldn-muted">No contacts yet.</p>
  </section>
  <section class="ldn-stack ldn-gap-sm" data-laadan-scope>
    <label class="ldn-field">Name <input type="text" name="name"></label>
    <label class="ldn-field">Note <textarea name="note"></textarea></label>
    <button type="button" class="ldn-btn ldn-btn-primary" data-laadan-action="a3">Add contact</button>
  </section>
</main>
```

Action definition stored on the server, not visible in the page:

```json
{ "id": "a3", "kind": "intent", "intent": "add_contact", "target": "contact-list", "payload": { "entity_type": "contact" }, "include": [], "scope_inputs": ["name", "note"] }
```

---

## 6. Action Protocol

### 6.1 Data attributes

The complete list of `data-laadan-*` attributes. All are written by server templates, never by the model.

| Attribute | Element | Value |
| :--- | :--- | :--- |
| `data-laadan-route` | App root `#ldn-app` | Current route |
| `data-laadan-action` | `button` | `^a[0-9]{1,6}$`, or `shell.regenerate` in the shell only |
| `data-laadan-scope` | `section` | No value |
| `data-laadan-include` | `button` | Space-separated `u-` IDs, at most 10 |

### 6.2 What the client script does on click

1. Find the closest element with `data-laadan-action` inside `#ldn-app` or the shell.
2. Collect `input`, `select`, and `textarea` elements with a `name` inside the closest `[data-laadan-scope]`. Text fields become strings, checkboxes become booleans.
3. For each ID in `data-laadan-include`, read the element's `value` (form fields) or `textContent` (others).
4. Send the envelope to `POST /_laadan/action` with `Content-Type: application/json`.
5. Disable the button until the response arrives, then apply the returned operations in order.

### 6.3 Request envelope

```json
{
  "v": 1,
  "route": "/whatsapp",
  "action": "a3",
  "values": { "name": "Ada Lovelace", "note": "Met at the workshop" },
  "included": {}
}
```

The server checks that the action exists on the stored page for `route`, that the keys of `values` match `scope_inputs`, and that the keys of `included` match `include`. Strings are limited to 2,000 characters.

### 6.4 Update proposal from the model

```json
{
  "kind": "update",
  "updates": [
    { "op": "remove", "target": "empty-hint" },
    {
      "op": "append", "target": "contact-list",
      "nodes": [
        { "type": "Card", "title": "Ada Lovelace", "children": [ { "type": "Text", "text": "Met at the workshop" } ] }
      ]
    }
  ],
  "entity_ops": [
    { "op": "create", "type": "contact", "attributes": { "name": "Ada Lovelace", "note": "Met at the workshop" } }
  ]
}
```

| `op` | Meaning | Rules |
| :--- | :--- | :--- |
| `replace` | Replace the target node | Exactly one node; it keeps the target's `id` |
| `append` | Add nodes as last children of the target | Target must be a container |
| `prepend` | Add nodes as first children of the target | Target must be a container |
| `remove` | Remove the target node | Not allowed on the page root |

The server applies valid updates to the stored page, so a later visit renders the same state.

### 6.5 Response

```json
{
  "v": 1,
  "status": "ok",
  "ops": [
    { "op": "remove", "target": "empty-hint" },
    { "op": "append", "target": "contact-list", "html": "<article class=\"ldn-card\"><h3>Ada Lovelace</h3><p>Met at the workshop</p></article>" }
  ]
}
```

* `status`: `ok`, `merged` (batched mode, no operations; see architecture, section 5), or `error` (contains one `replace` with a fallback fragment).
* Operations: `replace`, `append`, `prepend`, `remove`, and `reload` (no target; the client reloads the page).
* `html` values are produced by the compiler and have passed the output check. The client inserts them through the Trusted Types policy `laadan`.
* Planned: `morph`, which updates the target in place and keeps focus and scroll position.

---

## 7. API Response (JSON Mode)

```json
{
  "kind": "api",
  "status": 200,
  "body": { "contacts": [ { "id": "e_42", "name": "Ada Lovelace" } ] },
  "entity_ops": []
}
```

* `status` is one of 200, 201, 204, 400, 404, 409, 422.
* `body` is plain JSON (at most 64 KB, depth 8) and is sent as `application/json`. It is never rendered as HTML.
