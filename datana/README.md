# Handoff: Datana Solutions website

## Overview
This is a redesign of datanasolutions.com, which is currently a single long page. The new site is a multi-page consulting site with seven page types: Home, Services, Client work (an index plus three case studies), About, Contact, and Privacy/Terms. It aims to show engineering credibility through specifics and proof.

## About the design files
The files here are **design references built in HTML**. They show the intended look and behavior, but they are not production code. Rebuild them in the target codebase's framework and follow its patterns. If there is no codebase yet, pick a fitting stack. A static-site framework such as Astro or Next.js with static export works well, because the site is content-led with light interactivity.

- `Datana Solutions Site.html`: a self-contained build. Open it in any browser to see every page.
- `design/Datana Site.dc.html`: the readable source. The markup uses inline styles. The script block at the bottom holds the page content (`CASES`, `TEAM`, `PRIVACY`, `TERMS`) and the two diagram generators (`heroGraphic()`, `flowGraphic()`). To open it locally, serve the `design/` folder so `support.js` and `uploads/` resolve.
- `design/Datana Design Document.dc.html`: the visual spec (tokens, type, components, pages).
- `PROJECT_RULES.md`: the project rules. Rename it to `CLAUDE.md` and put it at the root of the new repo so Claude Code reads it automatically.

## Fidelity
**High-fidelity.** The colors, type, spacing, copy and animations are final. Match them exactly. All copy in the source is approved, so take it verbatim.

## Routes
The prototype uses hash routes (`#/services`). Change these to real paths in production.

- `/`: Home. Hero with the learning-loop diagram, services grid (S.01–S.06), proof section, CTA block.
- `/services`: Services. The six capabilities in detail, the data-flow diagram and a CTA block.
- `/work`: Client work index. A three-card ruled grid (Retail, FinTech, Healthcare), each with a headline metric, then a CTA block.
- `/work/retail`, `/work/fintech`, `/work/health`: case studies. Each has a tag, title, lede, three metrics, problem, numbered work steps (01–04), outcome, pull quote, and the inline "Facing something similar?" row.
- `/about`: About. Includes team bios: Gillian Villanueva, Ruben Arteaga (VP Data Engineering), and a third placeholder. Ends with a CTA block.
- `/contact`: Contact. Form (Name, Work email, Company, "What are you trying to figure out?") plus direct details. **No CTA block.**
- `/privacy`, `/terms`: legal pages. **No CTA block.** The full text is in `PRIVACY` / `TERMS` in the source.

Global elements:
- A sticky header, 16px/32px padding, with a background of `rgba(19,32,64,.88)` and `backdrop-filter: blur(12px)`. It has a bottom hairline, the logo at 42px tall, nav links (14px, `#9AA1AB`, hovering to `#E6E8EB`), and a mono outline CTA ("Start a conversation").
- A footer on every page.
- When the route changes, scroll to the top.

## Design tokens
Colors:
- Ground `#132040`, raised panel / CTA band `#17243D`, hover `#1A2A4C`, input / inset `#0A1625`.
- Text `#E6E8EB`, secondary `#9AA1AB`, body muted `#8A9099`, meta `#6E7681`, tertiary `#C3C8D0`.
- Hairline `rgba(230,232,235,.08)`. Control borders `rgba(230,232,235,.12–.22)`.
- Accent `#E5348C`, hover `#F4699F`, pressed `#C82778`. Selection `rgba(229,52,140,.3)`.
- No gradients, no cyan, no shadows.

Type (Google Fonts):
- IBM Plex Sans in weights 300, 400 and 500. Base size 16px, line-height 1.62.
  - Display: `clamp(38px,5.2vw,68px)`, weight 400, letter-spacing −.03em.
  - Section headings: `clamp(26px,2.8vw,34px)`, weight 400, letter-spacing −.02em.
  - Card titles: 19px, weight 500.
  - Body: 15.5–17px, weight 300.
- IBM Plex Mono in weights 400 and 500, for every number, index (S.01), label and piece of metadata.
  - Labels: 11.5–12.5px, uppercase, letter-spacing .06–.1em.
- Headings never go above weight 500.

Layout:
- Container max-width 1200px with 32px side padding.
- Sections use 88–96px vertical padding.
- Card grids are ruled: `gap: 1px` over a hairline background with a 1px hairline border. Each cell has the ground color and hovers to `#1A2A4C`. Grids use `repeat(auto-fit, minmax(206–300px, 1fr))`.
- Radius is 4px on buttons and 3px on inputs. Nothing else is rounded.

Components:
- Primary button: 13px/22px padding, `#E5348C` fill, white text at 15px, weight 500. Hovers to `#C82778`. Use only one per page, plus the contact submit button.
- Secondary button: 1px `rgba(230,232,235,.2)` border and `#E6E8EB` text. The border turns accent on hover.
- Input: `#0A1625` background, 1px `rgba(230,232,235,.16)` border, 12px/13px padding. The label above is mono, 11.5px, uppercase, `#6E7681`.

## Diagrams (SVG + SMIL in the source)
- **Hero (`heroGraphic()`)**: a closed loop running INPUT → MODEL → ACTION → LEARN → INPUT, with the output branching to BUSINESS OPERATION. Pulses travel the path, and magenta appears only on the active segment. Node labels are in mono.
- **Flow (`flowGraphic()`)**: six sources feed three models, which fan out to ACTIONS and DECISIONS. Dots animate along the edges.
- For production, you can keep them as inline SVG/SMIL or port them to CSS or JS animation. Honor `prefers-reduced-motion`.

## Behavior
- Contact form: the submit handler currently only swaps in a confirmation state. Connect it to a real endpoint (email service or CRM). Name and work email are required.
- Nothing is loaded from external data. All content is static.

## Content rules
- There are exactly four CTA blocks: Home, Services, Client work and About.
- Predictive Modelling produces a number that people act on. AI Agents execute multi-step workflows end to end. Keep their copy separate so they don't overlap.
- Avoid reassurance or hype copy.

## Open items
- The third team bio is a placeholder.
- The Databricks partnership wording still needs confirming.
- The contact form backend needs building.

## Assets
- Logo: `design/uploads/logo-1789148846326-lkk3.png`, shown at 42px tall.
- There is no other imagery. The diagrams are code.
