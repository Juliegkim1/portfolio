"""Stripe integration: create customers, invoices, and sync payment status."""
from datetime import date, timedelta
from typing import Optional

import stripe

from config import STRIPE_SECRET_KEY
from models import Invoice, Project


class StripeService:
    def __init__(self, api_key: str = STRIPE_SECRET_KEY):
        stripe.api_key = api_key

    def get_or_create_customer(self, project: Project) -> str:
        """Find existing Stripe customer by email or create a new one. Returns customer ID."""
        existing = stripe.Customer.list(email=project.customer_email, limit=1)
        if existing.data:
            return existing.data[0].id
        customer = stripe.Customer.create(
            name=project.customer_name,
            email=project.customer_email,
            phone=project.customer_phone,
            metadata={"project_name": project.name, "property_address": project.property_address},
        )
        return customer.id

    def create_invoice(
        self,
        project: Project,
        invoice: Invoice,
        days_until_due: int = 30,
    ) -> dict:
        """
        Create a Stripe invoice with a line item for the given Invoice model.
        Returns dict with stripe_invoice_id, stripe_invoice_url, status.
        """
        customer_id = self.get_or_create_customer(project)

        # Create invoice item
        stripe.InvoiceItem.create(
            customer=customer_id,
            amount=int(invoice.total * 100),  # cents
            currency="usd",
            description=invoice.description,
            metadata={
                "project_name": project.name,
                "invoice_number": invoice.invoice_number,
                "property_address": project.property_address,
            },
        )

        # Create the invoice
        stripe_inv = stripe.Invoice.create(
            customer=customer_id,
            collection_method="send_invoice",
            days_until_due=days_until_due,
            metadata={
                "project_name": project.name,
                "invoice_number": invoice.invoice_number,
                "property_address": project.property_address,
                "project_type": project.project_type,
            },
            description=f"{project.name} — {invoice.description}",
        )

        # Finalize so it gets a hosted URL
        finalized = stripe.Invoice.finalize_invoice(stripe_inv.id)

        return {
            "stripe_invoice_id": finalized.id,
            "stripe_invoice_url": finalized.hosted_invoice_url or "",
            "status": finalized.status,
        }

    def sync_invoice_status(self, stripe_invoice_id: str) -> dict:
        """Fetch latest status from Stripe. Returns dict with status and payment_date."""
        inv = stripe.Invoice.retrieve(stripe_invoice_id)
        payment_date = None
        if inv.status == "paid" and inv.status_transitions and inv.status_transitions.paid_at:
            payment_date = date.fromtimestamp(inv.status_transitions.paid_at).isoformat()
        return {
            "status": inv.status,
            "payment_date": payment_date,
            "amount_paid": inv.amount_paid / 100,
        }

    def void_invoice(self, stripe_invoice_id: str) -> dict:
        """Void a Stripe invoice."""
        inv = stripe.Invoice.void_invoice(stripe_invoice_id)
        return {"status": inv.status}

    def list_project_invoices(self, customer_email: str) -> list:
        """List all Stripe invoices for a customer email."""
        customers = stripe.Customer.list(email=customer_email, limit=1)
        if not customers.data:
            return []
        invoices = stripe.Invoice.list(customer=customers.data[0].id)
        return [
            {
                "stripe_id": inv.id,
                "number": inv.number,
                "amount": inv.amount_due / 100,
                "status": inv.status,
                "due_date": date.fromtimestamp(inv.due_date).isoformat() if inv.due_date else None,
                "url": inv.hosted_invoice_url,
            }
            for inv in invoices.data
        ]
