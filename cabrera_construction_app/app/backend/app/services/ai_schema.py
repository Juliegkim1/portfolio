"""Prompt + response-schema definitions for project/estimate extraction,
shared across every AI provider (Gemini, Anthropic, OpenAI) so the
instructions aren't maintained three times and results stay comparable
regardless of which provider actually answered. gemini_service.py keeps its
own schema dicts (Gemini's `responseSchema` dialect — the same shape as
here but with UPPERCASE type names) since that path is already proven in
production; EXTRACTION_SCHEMA/HISTORICAL_SCHEMA below are the plain-
JSON-Schema versions anthropic_service.py and openai_service.py use
directly. Every field is listed in `required` with nullable types (e.g.
`["string", "null"]`) rather than left optional — OpenAI's Structured
Outputs "strict" mode requires this shape; Anthropic's tool-use schema
tolerates it fine too, so one schema shape serves both.
"""

from __future__ import annotations

EXTRACTION_PROMPT = (
    "This document is either a QuickBooks-exported estimate or informal notes written by a "
    "general contractor (sometimes handwritten-style, with typos, OCR garbling, shorthand, or "
    "mixed English/Spanish). Extract a structured project estimate from it.\n\n"
    "Rules:\n"
    "- Only extract information actually present in the document. Leave a field empty "
    "(or omit it) rather than inventing a customer name, address, phone, or email that "
    "isn't there.\n"
    "- line_items are the COST BREAKDOWN (materials/labor/demo), not the payment schedule. "
    "Every priced item in a materials/labor/demo breakdown becomes one line item. Classify "
    "each into exactly one section: 'demolition' (demo/removal/prep work), 'materials', "
    "'labor', or 'additional_work' (anything else, e.g. a line that's clearly a flat task "
    "without materials/labor split out). If a line bundles labor and material together with "
    "one price, you can put it under whichever section best matches its main description, or "
    "'additional_work' if ambiguous. qty defaults to 1 and unit to 'ea' when the document "
    "doesn't break those out separately — put the full line price in unit_price in that case.\n"
    "- milestones are the PAYMENT SCHEDULE (how/when the client pays), a SEPARATE concept from "
    "line_items — a document can have a cost breakdown, a payment schedule, both, or neither. "
    "If the document lists a deposit followed by numbered payments/phases with their own "
    "dollar amounts (e.g. 'Deposit $1,000', '1. Payment $5,000 — demo and prep', '2. Rough "
    "framing $10,000', ...), extract EACH as its own milestone: number starts at 0 for the "
    "deposit and increases in the order listed; amount is that line's dollar figure; title is "
    "a SHORT (under 60 characters) clean label for the phase — unlike payment_terms/"
    "warranty_terms below, DO NOT copy garbled source text verbatim here: normalize obvious "
    "typos/OCR errors into standard construction terms (e.g. 'FRAIMING RAUGE' -> 'Rough "
    "Framing', 'INSOLATION AND DRAYWALL' -> 'Insulation & Drywall', 'PLUMBING AND ELECTRICAL "
    "RAUGE' -> 'Plumbing & Electrical Rough-In'). Do not also duplicate these payment-schedule "
    "entries as line_items — they're the same money described two different ways (what for vs. "
    "when paid), not two different costs.\n"
    "- contract_date, payment_terms, warranty_terms: contract metadata if present. Copy "
    "payment_terms/warranty_terms language close to verbatim (these are terms, not prose to "
    "polish) — garbled OCR text is fine here since it's quoting the source, unlike milestone "
    "titles above which need to be scannable at a glance.\n"
    "- scope_text: write a clear 2-4 sentence project scope description covering the "
    "actual work, as if for a contract's project description field — not a copy of the "
    "line items verbatim.\n"
    "- total: the document's own stated total if present; otherwise the sum of all line "
    "item prices.\n"
)

HISTORICAL_PROMPT = (
    "These documents are the complete file for a residential construction project that was "
    "created BEFORE this app existed. Extract a complete historical record from them so the "
    "project's contact info, scope, and payment schedule can be reconstructed. These documents "
    "may be some combination of a signed contract, a formal estimate, a formal Scope & Payment "
    "Schedule — AND/OR informal notes the contractor wrote for himself (a DOCX with no "
    "particular structure, sometimes handwritten-style, with typos, shorthand, abbreviations, or "
    "mixed English/Spanish — extract the intent, don't fix or judge the writing). A folder is "
    "often a mix of several of these; an informal notes file is frequently where the real "
    "payment-schedule detail actually lives, even when a more formal-looking contract or estimate "
    "is also present — don't let the presence of a polished-looking document cause you to skip "
    "over what a rougher one actually says. Combine information across all of them into one "
    "result rather than treating any single file as more authoritative by default.\n\n"
    "Rules:\n"
    "- Only extract information actually present in the documents. Leave a field empty rather "
    "than inventing a customer name, address, phone, email, contract date, or payment terms that "
    "aren't there.\n"
    "- Every priced item on the estimate becomes one line item, classified into 'demolition', "
    "'materials', 'labor', or 'additional_work' as best fits.\n"
    "- milestones are the PAYMENT SCHEDULE (how/when the client pays), a SEPARATE concept from "
    "line_items (what the work costs) — don't duplicate payment-schedule entries as line_items. "
    "Each milestone (e.g. 'Deposit', 'Rough-in complete', 'Final payment') gets its own amount. "
    "number starts at 0 for the initial deposit/payment and increases in the order they appear. "
    "If no payment schedule document is present, leave milestones empty rather than guessing a "
    "schedule. title is a SHORT (under 60 characters) clean label — normalize obvious typos/OCR "
    "errors into standard construction terms (e.g. 'FRAIMING RAUGE' -> 'Rough Framing') rather "
    "than copying garbled source text verbatim; that's for payment_terms/warranty_terms below, "
    "not milestone titles, which need to be scannable at a glance.\n"
    "- contract_date: the date the contract was signed, if stated.\n"
    "- payment_terms / warranty_terms: copy the actual contract language if present, don't "
    "paraphrase.\n"
    "- scope_text: a clear 2-4 sentence project scope description covering the actual work.\n"
    "- total: the contract's stated total if present; otherwise the sum of all line item prices.\n"
)

_LINE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "section": {"type": "string", "enum": ["demolition", "materials", "labor", "additional_work"]},
        "description": {"type": "string"},
        "qty": {"type": "number"},
        "unit": {"type": "string"},
        "unit_price": {"type": "number"},
    },
    "required": ["section", "description", "qty", "unit", "unit_price"],
    "additionalProperties": False,
}

_MILESTONE_SCHEMA = {
    "type": "object",
    "properties": {
        "number": {"type": "integer"},
        "title": {"type": "string"},
        "amount": {"type": "number"},
        "due_date": {"type": ["string", "null"], "description": "ISO date (YYYY-MM-DD) if known, else null"},
    },
    "required": ["number", "title", "amount", "due_date"],
    "additionalProperties": False,
}


def _result_schema(found_description: str) -> dict:
    return {
        "type": "object",
        "properties": {
            "found": {"type": "boolean", "description": found_description},
            "customer_name": {"type": ["string", "null"]},
            "customer_phone": {"type": ["string", "null"]},
            "customer_email": {"type": ["string", "null"]},
            "property_address": {"type": ["string", "null"]},
            "scope_text": {"type": ["string", "null"]},
            "total": {"type": ["number", "null"]},
            "contract_date": {"type": ["string", "null"], "description": "ISO date (YYYY-MM-DD) if known, else null"},
            "payment_terms": {"type": ["string", "null"]},
            "warranty_terms": {"type": ["string", "null"]},
            "line_items": {"type": "array", "items": _LINE_ITEM_SCHEMA},
            "milestones": {"type": "array", "items": _MILESTONE_SCHEMA},
        },
        "required": [
            "found", "customer_name", "customer_phone", "customer_email", "property_address",
            "scope_text", "total", "contract_date", "payment_terms", "warranty_terms",
            "line_items", "milestones",
        ],
        "additionalProperties": False,
    }


EXTRACTION_SCHEMA = _result_schema("false only if this document has no usable estimate/job information at all")
HISTORICAL_SCHEMA = _result_schema("false only if these documents have no usable project information at all")
