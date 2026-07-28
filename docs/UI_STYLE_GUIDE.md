# Chemical Trade Copilot UI Style Guide

## Purpose and product posture

This document is the implementation contract for the Phase Three Streamlit UI. The
approved Chinese wireframes are design references; the shipped interface and email
draft are English.

The product should feel like an editorial technical brief: calm, precise, and easy to
verify. It must not resemble a dashboard, marketplace, CRM, generic chatbot, or public
product catalog.

The primary reading order is:

1. Can the inquiry be answered technically?
2. What exact evidence supports the answer?
3. What blocks a commercial quotation or compliant reply?
4. What should the user ask or confirm next?
5. What can be copied into an English customer reply?

## Visual tokens

| Token | Value | Use |
|---|---:|---|
| Paper | `#F2EFE7` | Main page background |
| Surface | `#FBFAF6` | Text areas, evidence groups, email editor |
| Mineral ink | `#102B27` | Primary text and primary actions |
| Verdigris | `#316A5D` | Verified states and evidence links |
| Pale verdigris | `#E1EBE6` | Source rows and supported-state surfaces |
| Aged brass | `#A78349` | Confirmation-needed states and cautions |
| Rule | `#D7D0C3` | Dividers and quiet borders |
| Body text | `#465750` | Long-form copy |
| Muted text | `#6F7A75` | Metadata and secondary labels |
| Guardrail | `#8D4B3B` | Fail-closed notices only |

Use warm off-white surfaces instead of pure white. Do not use gradients, glassmorphism,
neon colors, decorative molecule illustrations, laboratory stock photos, or generated
chemical imagery.

## Typography and numeric data

- Editorial headings: Georgia with a serif fallback.
- Interface text: Inter, Segoe UI, Arial, or the system sans-serif stack.
- Verified numbers: sans-serif, upright, `font-style: normal`, and
  `font-variant-numeric: tabular-nums`.
- A temperature must never appear as a decorative hero metric.
- A cured-system result must give equal visual weight to property, value, curing agent,
  mix ratio, cure schedule, test method, document, and physical page.

## Layout

- One centered reading column; target content width `960–1040px`.
- No permanent sidebar.
- Use horizontal rules and whitespace before introducing another card.
- Reserve two-column layouts for short comparisons such as customer inputs versus
  internal confirmations. Collapse to one column on narrow screens.
- Keep one primary action per section.
- Progressive disclosure is preferred: source preview and full email editing open only
  when requested.

## Core states

### Inquiry entry

- One large free-text input; do not force a novice user through a long form.
- Beneath the input, provide a quiet hint listing useful details: end use, key technical
  requirement, destination country or port, quantity, delivery window, Incoterm,
  packaging, and certification need.
- Example inquiries are allowed for the Demo but remain visually secondary.

### Analysis in progress

- Show one honest status: validating TDS/SDS evidence and local guardrails.
- Do not show invented percentages or an internal step-by-step performance.
- State that unsupported output will fail closed.

### Evidence-supported result

- Lead with the product and a plain business conclusion such as “Technical reply ready;
  quotation inputs still required.”
- Present technical, compliance, quotation, and logistics readiness as one restrained
  decision line, not dashboard tiles.
- Show one compact verified-fact group with all applicable conditions.
- Follow with two checklists: information to obtain from the customer and information
  to confirm internally.
- Show the available document pack and mark missing documents explicitly. A COA is
  batch-specific and must be shown as unavailable unless a real COA is supplied.

### Insufficient evidence and fail-closed output

- Never recommend a product or display an unverified technical value.
- Explain the decisive missing evidence, then provide focused customer questions.
- A model-validation failure uses the same state with a short guardrail notice. It does
  not receive a separate page.

## Source preview and image interaction

- Only authentic PDF page renders are used as imagery.
- The source thumbnail is clickable and opens a large modal viewer.
- The viewer provides visible `Zoom in`, `Zoom out`, and `Reset` controls.
- Zoom range: `50%–250%`; increment: `25%`.
- Clicking the page toggles between fit-to-view and `150%`.
- When zoomed beyond the viewport, the page can be panned with scrollbars.
- The source filename, document date or revision, jurisdiction, product, and physical
  page remain visible alongside the image.
- Viewer HTML and JavaScript are static trusted application code. User input, model
  output, and PDF text are never interpolated as executable HTML.

## English reply draft

- The draft is editable and copyable but never sent automatically.
- It may use only the evidence-gated analysis and deterministic placeholders.
- It must not invent or confirm price, currency, stock, MOQ, lead time, freight,
  packaging, payment terms, certification, or availability.
- It must not say a document is attached unless the user has actually selected that
  document for sending.
- Temperature values remain in the structured verified-fact group and are not repeated
  in free narrative.

## Responsive and accessibility rules

- Maintain readable contrast for text, verified states, warnings, and buttons.
- All interactive controls require visible text labels and keyboard focus styles.
- Do not rely on color alone; pair color with status wording.
- The PDF page uses descriptive alternative text.
- At widths below `820px`, multi-column groups stack without changing the reading order.

## Explicit non-goals

- No account, navigation hierarchy, admin shell, file upload, analytics dashboard,
  supplier marketplace, live inventory, live pricing, or email integration.
- No generic chat transcript.
- No hidden claim that old or jurisdiction-specific documents are globally current.
- No redesign of retrieval, evidence validation, or the verified-fact whitelist.
