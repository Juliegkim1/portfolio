"""Best-effort parser for uploaded (QuickBooks) estimate PDFs.

Extraction is heuristic by design — the app always shows the result in the
existing editable line-item table and a client-info card (see
ui/screens/estimate_screen.py) before anything is saved, so this only needs
to get close enough to edit/correct.
"""
import re
from typing import Dict, List, Optional

import pdfplumber

DEFAULT_SECTION = "ADDITIONAL WORK"
_SECTION_KEYWORDS = {
    "DEMOLITION/PREPARATION": ("demo", "prep", "removal"),
    "MATERIALS": ("material", "supply", "supplies"),
    "LABOR": ("labor", "install", "installation"),
}
_MONEY_RE = re.compile(r"^\$?\s*-?\d[\d,]*\.?\d{0,2}$")
_SKIP_DESCRIPTIONS = {"", "description", "activity", "item", "total", "subtotal", "tax"}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_BILL_TO_RE = re.compile(r"\b(bill\s*to|customer|client|sold\s*to)\b", re.IGNORECASE)


class EstimateParserService:
    """Extracts scope-of-work line items and client info from an uploaded estimate PDF."""

    def parse(self, pdf_path: str) -> Dict:
        rows: List[Dict] = []
        client_info = {"name": "", "address": "", "phone": "", "email": ""}
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    rows.extend(self._rows_from_table(table))
            if pdf.pages:
                found = self._extract_client_info(pdf.pages[0].extract_text() or "")
                client_info.update({k: v for k, v in found.items() if v})
        return {"line_items": rows, "client_info": client_info}

    def _extract_client_info(self, text: str) -> Dict:
        """Scoped to the text right after a "Bill To"/"Customer" label rather than
        the whole page — the page also contains the contractor's own contact
        info (letterhead), and a whole-page search would grab that instead."""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        info = {"name": "", "address": "", "phone": "", "email": ""}

        for i, line in enumerate(lines):
            if _BILL_TO_RE.search(line):
                # Take up to the next few non-empty lines as name/address/contact —
                # skip a line that's just the matched label itself (e.g. "Bill To:").
                after_label = _BILL_TO_RE.sub("", line).strip(" :—-")
                block = ([after_label] if after_label else []) + lines[i + 1:i + 7]
                # Drop empty lines, other section labels caught in the same merged
                # line (e.g. a "JOB SITE"/"PROJECT TYPE" heading from an adjacent
                # column — always ALL CAPS, unlike a real name or address), and
                # any leftover "bill to"-style label text.
                block = [c for c in block
                         if c and not _BILL_TO_RE.search(c) and not c.isupper()]
                block_text = " ".join(block)

                email_match = _EMAIL_RE.search(block_text)
                if email_match:
                    info["email"] = email_match.group(0)
                phone_match = _PHONE_RE.search(block_text)
                if phone_match:
                    info["phone"] = phone_match.group(0)

                # Name/address candidates: drop any line that's just the phone
                # or email we already captured out of the block.
                rest = [c for c in block
                        if c != info["email"] and c != info["phone"]]
                if rest:
                    info["name"] = rest[0]
                if len(rest) > 1:
                    info["address"] = ", ".join(rest[1:3])
                break

        return info

    def _rows_from_table(self, table: List[List[Optional[str]]]) -> List[Dict]:
        if not table:
            return []
        header = [(c or "").strip().lower() for c in table[0]]
        col = self._map_columns(header)
        body = table[1:] if col else table
        items = []
        for raw in body:
            item = self._row_from_cells(raw, col)
            if item:
                items.append(item)
        return items

    def _map_columns(self, header: List[str]) -> Dict[str, int]:
        col = {}
        for i, name in enumerate(header):
            if not name:
                continue
            if "desc" in name or "activity" in name or "item" in name:
                col.setdefault("description", i)
            elif "qty" in name or "quantity" in name:
                col.setdefault("qty", i)
            elif "unit" in name and "price" not in name and "rate" not in name:
                col.setdefault("unit", i)
            elif "rate" in name or "price" in name or "cost" in name:
                col.setdefault("unit_price", i)
        return col if "description" in col else {}

    def _row_from_cells(self, cells: List[Optional[str]], col: Dict[str, int]) -> Optional[Dict]:
        cells = [(c or "").strip() for c in cells]
        if not any(cells):
            return None

        if col:
            description = cells[col["description"]] if col["description"] < len(cells) else ""
            qty = self._qty_or_default(cells, col)
            unit = cells[col["unit"]] if "unit" in col and col["unit"] < len(cells) else ""
            unit_price = self._price_from(cells, col)
        else:
            # No recognizable header row: longest text cell is the description,
            # the last money-looking cell is the unit price.
            texts = [c for c in cells if c and not _MONEY_RE.match(c.replace(",", ""))]
            money = [c for c in cells if c and _MONEY_RE.match(c.replace(",", ""))]
            description = max(texts, key=len) if texts else ""
            qty, unit = 1.0, ""
            unit_price = self._to_float(money[-1]) if money else 0.0

        description = description.strip()
        if description.lower() in _SKIP_DESCRIPTIONS:
            return None

        return {
            "section": self._guess_section(description),
            "description": description,
            "qty": qty or 1.0,
            "unit": unit or "ea",
            "unit_price": unit_price or 0.0,
        }

    def _qty_or_default(self, cells: List[str], col: Dict[str, int]) -> float:
        if "qty" in col and col["qty"] < len(cells):
            return self._to_float(cells[col["qty"]]) or 1.0
        return 1.0

    def _price_from(self, cells: List[str], col: Dict[str, int]) -> float:
        if "unit_price" in col and col["unit_price"] < len(cells):
            return self._to_float(cells[col["unit_price"]])
        return 0.0

    def _guess_section(self, description: str) -> str:
        lowered = description.lower()
        for section, keywords in _SECTION_KEYWORDS.items():
            if any(kw in lowered for kw in keywords):
                return section
        return DEFAULT_SECTION

    def _to_float(self, text: str) -> float:
        if not text:
            return 0.0
        try:
            return float(text.replace("$", "").replace(",", "").strip())
        except ValueError:
            return 0.0
