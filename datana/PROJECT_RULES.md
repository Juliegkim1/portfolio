# Datana Solutions site — project rules

Working file: `Datana Site.dc.html` (single DC, hash routes). Spec: `Datana Design Document.dc.html`. Standalone bundle: `Datana Solutions Site.html` (re-bundle after every change to the working file).

## Voice
- Engineering credibility, specifics, proof. No reassurance copy ("don't worry", "we've got you"), no hype.
- Keep user-supplied copy verbatim.
- One CTA block per page (Home, Services, Client work, About). Contact and legal pages have none.

## Type
- IBM Plex Sans (300 body, 400 headings, 500 small titles). Never heavier than 500 for headings.
- IBM Plex Mono for every number, label, index (S.01), metadata, nav CTA. Uppercase labels at 11.5–12.5px, letter-spacing .06–.1em.

## Color (hex literals, inline styles only)
- Ground `#132040` (matches datanasolutions.com). Raised panel `#17243D`. Hover `#1A2A4C`. Inset/input `#0A1625`.
- Text `#E6E8EB`; secondary `#9AA1AB`; body-muted `#8A9099`; meta `#6E7681`.
- Hairlines `rgba(230,232,235,.08)` (default), `.12–.22` for control borders.
- Accent magenta `#E5348C` (hover `#F4699F`, pressed `#C82778`). Thin accent only: the single filled CTA, rule markers, mono labels. Never a flood. No cyan, no gradients.

## Layout
- Container max-width 1200px, 32px side padding. Sections 88–96px vertical.
- Card grids: 1px gap over a hairline background (ruled grid), not floating rounded cards.
- Radius 4px buttons, 3px inputs. No shadows.

## Content structure
- Pages: Home, Services, Client work (+ retail, fintech, health cases), About, Contact, Privacy/Terms.
- Capabilities: Predictive Modelling = produces a number humans act on. AI Agents = executes multi-step workflows end to end. Keep them non-overlapping.
- Team: Gillian Villanueva, Ruben Arteaga (VP Data Engineering), third bio placeholder.
- Logo `uploads/logo-1789148846326-lkk3.png` at 42px tall.

## Diagrams
- Hero: closed loop INPUT → MODEL → ACTION → LEARN → INPUT, output branches to BUSINESS OPERATION.
- Flow: six sources → three models → ACTIONS and DECISIONS.
- SVG + SMIL animation, built in `heroGraphic()` / `flowGraphic()` in the logic class. Mono labels, magenta only on the active path.
