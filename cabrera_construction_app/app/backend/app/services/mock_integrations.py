"""Stand-ins for the not-yet-built QuickBooks / Google Drive+Sheets integrations.

CLAUDE.md's integration order builds these in a later phase against the real
APIs. Keeping them as small, named functions with the same call shape the
real versions will have means swapping in real API calls later is a
localized change, not a rewrite of the routers that call them.
"""

from __future__ import annotations

import datetime as dt
import hashlib

from ..schemas import EstimateFetchResult, EstimateLineItemIn


def _with_total(result: EstimateFetchResult) -> EstimateFetchResult:
    subtotal = round(sum(li.qty * li.unit_price for li in result.line_items), 2)
    result.total = round(subtotal + subtotal * result.tax_rate + result.permit_fees - result.discount, 2)
    return result

# A couple of estimate numbers "exist" in the mock QuickBooks sandbox so the
# Estimate Upload screen's happy path can be demoed end to end. Any other
# number falls through to "not found" -> the PDF-upload fallback.
_MOCK_QUICKBOOKS_ESTIMATES: dict[str, EstimateFetchResult] = {
    "1042": EstimateFetchResult(
        found=True,
        estimate_number="1042",
        customer_name="Maria Delgado",
        customer_phone="(510) 555-0142",
        customer_email="maria.delgado@example.com",
        property_address="148 Willow Creek Dr, Fremont, CA 94536",
        date_issued=dt.date(2026, 8, 3),
        scope_text="Full kitchen remodel: demo existing cabinetry and flooring, reroute plumbing for "
        "island sink, new cabinets/countertops/backsplash, new flooring, repaint.",
        tax_rate=0.0875,
        permit_fees=450.0,
        discount=0.0,
        line_items=[
            EstimateLineItemIn(section="demolition", description="Remove existing cabinets and countertops", qty=1, unit="ea", unit_price=1200),
            EstimateLineItemIn(section="demolition", description="Remove existing flooring", qty=180, unit="sq ft", unit_price=4.5),
            EstimateLineItemIn(section="materials", description="Custom cabinetry", qty=1, unit="ea", unit_price=14500),
            EstimateLineItemIn(section="materials", description="Quartz countertops", qty=42, unit="sq ft", unit_price=95),
            EstimateLineItemIn(section="materials", description="Luxury vinyl plank flooring", qty=180, unit="sq ft", unit_price=6.75),
            EstimateLineItemIn(section="labor", description="Cabinet installation", qty=24, unit="hr", unit_price=95),
            EstimateLineItemIn(section="labor", description="Plumbing rework for island", qty=10, unit="hr", unit_price=140),
            EstimateLineItemIn(section="labor", description="Flooring installation", qty=180, unit="sq ft", unit_price=5.5),
            EstimateLineItemIn(section="additional_work", description="Electrical for under-cabinet lighting", qty=1, unit="ea", unit_price=1800),
        ],
        retrieved_at=dt.datetime.now(),
    ),
    "2091": EstimateFetchResult(
        found=True,
        estimate_number="2091",
        customer_name="David Nguyen",
        customer_phone="(408) 555-0188",
        customer_email="d.nguyen@example.com",
        property_address="2217 Camino Real, San Jose, CA 95126",
        date_issued=dt.date(2026, 9, 1),
        scope_text="Primary bathroom remodel: demo existing tub/shower and tile, new walk-in shower, "
        "new vanity and fixtures, waterproofing and tile work.",
        tax_rate=0.0925,
        permit_fees=300.0,
        discount=250.0,
        line_items=[
            EstimateLineItemIn(section="demolition", description="Demo tub, shower enclosure and tile", qty=1, unit="ea", unit_price=950),
            EstimateLineItemIn(section="materials", description="Walk-in shower kit and glass panel", qty=1, unit="ea", unit_price=4200),
            EstimateLineItemIn(section="materials", description="Vanity, sink and fixtures", qty=1, unit="ea", unit_price=2600),
            EstimateLineItemIn(section="materials", description="Porcelain tile", qty=120, unit="sq ft", unit_price=7.25),
            EstimateLineItemIn(section="labor", description="Waterproofing and tile setting", qty=32, unit="hr", unit_price=90),
            EstimateLineItemIn(section="labor", description="Plumbing fixture installation", qty=12, unit="hr", unit_price=140),
            EstimateLineItemIn(section="additional_work", description="Exhaust fan replacement", qty=1, unit="ea", unit_price=380),
        ],
        retrieved_at=dt.datetime.now(),
    ),
}


def lookup_quickbooks_estimate(raw_number: str) -> EstimateFetchResult:
    """Accepts '1042', 'EST-1042' or '#1042', stripping the prefix before matching."""
    number = raw_number.strip().upper().removeprefix("EST-").removeprefix("#").lstrip("0") or "0"
    # also try the un-stripped-leading-zero form for exact fixture keys
    for candidate in {raw_number.strip(), number}:
        result = _MOCK_QUICKBOOKS_ESTIMATES.get(candidate)
        if result:
            return _with_total(result.model_copy(deep=True))
    return EstimateFetchResult(found=False, estimate_number=raw_number)


def mock_parse_estimate_pdf(filename: str) -> EstimateFetchResult:
    """Placeholder for pdfplumber-based parsing of an uploaded QuickBooks estimate PDF.

    Returns a fixed demo extraction so the upload-fallback UI has something
    real to show; wiring in pdfplumber against real exported PDFs is a later step.
    """
    return _with_total(EstimateFetchResult(
        found=True,
        estimate_number=f"PDF-{filename[:20]}",
        customer_name="Amara Okafor",
        customer_phone="(415) 555-0199",
        customer_email="amara.okafor@example.com",
        property_address="905 Panoramic Way, Berkeley, CA 94704",
        date_issued=dt.date.today(),
        scope_text="Deck rebuild and exterior repaint (parsed from uploaded PDF — demo extraction).",
        tax_rate=0.0875,
        permit_fees=600.0,
        discount=0.0,
        line_items=[
            EstimateLineItemIn(section="demolition", description="Remove existing deck", qty=1, unit="ea", unit_price=1400),
            EstimateLineItemIn(section="materials", description="Composite decking and railing", qty=1, unit="ea", unit_price=9800),
            EstimateLineItemIn(section="labor", description="Deck framing and installation", qty=40, unit="hr", unit_price=95),
            EstimateLineItemIn(section="additional_work", description="Exterior repaint", qty=1, unit="ea", unit_price=3200),
        ],
        retrieved_at=dt.datetime.now(),
    ))


def _fake_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]
    return digest


def create_drive_folder(customer_name: str, street: str, project_type: str) -> str:
    return f"drive-folder-{_fake_id('folder', customer_name, street, project_type)}"


def create_sheet(name: str) -> str:
    return f"sheet-{_fake_id('sheet', name)}"
