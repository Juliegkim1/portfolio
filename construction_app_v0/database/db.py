import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import List, Optional

from config import DATABASE_URL
from models import (Project, Estimate, EstimateLineItem, PaymentScheduleItem, Invoice,
                     Contract, ChangeOrder)


class Database:
    def __init__(self, db_path: str = DATABASE_URL):
        self.db_path = db_path
        self._init_schema()
        self._migrate()

    @property
    def _is_pg(self) -> bool:
        return self.db_path.startswith(("postgresql://", "postgres://"))

    def _q(self, sql: str) -> str:
        """Translate SQLite ? placeholders to PostgreSQL %s."""
        if self._is_pg:
            return sql.replace("?", "%s")
        return sql

    def _lastid(self, cursor) -> int:
        """Return the last inserted row id for both drivers."""
        if self._is_pg:
            # cursor_factory is RealDictCursor (see _conn), so rows are
            # dict-like — index by the "id" column name, not position.
            return cursor.fetchone()["id"]
        return cursor.lastrowid

    @contextmanager
    def _conn(self):
        if self._is_pg:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(self.db_path)
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_schema(self):
        if self._is_pg:
            statements = [
                """CREATE TABLE IF NOT EXISTS projects (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    property_address TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    customer_phone TEXT,
                    customer_email TEXT,
                    project_type TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    duration_days INTEGER DEFAULT NULL,
                    status TEXT DEFAULT 'active',
                    notes TEXT DEFAULT '',
                    drive_folder_id TEXT,
                    drive_invoices_folder_id TEXT,
                    drive_estimates_folder_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS estimates (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    estimate_number TEXT NOT NULL,
                    date_issued TEXT NOT NULL,
                    valid_until TEXT NOT NULL,
                    prepared_by TEXT,
                    tax_rate REAL DEFAULT 0,
                    permit_fees REAL DEFAULT 0,
                    discount REAL DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    drive_file_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS estimate_line_items (
                    id SERIAL PRIMARY KEY,
                    estimate_id INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
                    section TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    qty REAL NOT NULL DEFAULT 1,
                    unit TEXT DEFAULT 'ea',
                    unit_price REAL NOT NULL DEFAULT 0
                )""",
                """CREATE TABLE IF NOT EXISTS payment_schedule (
                    id SERIAL PRIMARY KEY,
                    estimate_id INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
                    payment_number INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    description TEXT NOT NULL,
                    due_date TEXT,
                    amount REAL NOT NULL DEFAULT 0,
                    status TEXT DEFAULT 'Pending'
                )""",
                """CREATE TABLE IF NOT EXISTS invoices (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    estimate_id INTEGER REFERENCES estimates(id),
                    invoice_number TEXT NOT NULL,
                    stripe_invoice_id TEXT,
                    stripe_invoice_url TEXT,
                    customer_name TEXT NOT NULL,
                    customer_email TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL DEFAULT 0,
                    tax_amount REAL DEFAULT 0,
                    date_issued TEXT,
                    due_date TEXT,
                    status TEXT DEFAULT 'draft',
                    payment_date TEXT,
                    notes TEXT DEFAULT '',
                    drive_file_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS contracts (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    estimate_id INTEGER REFERENCES estimates(id),
                    contract_number TEXT NOT NULL,
                    pdf_path TEXT,
                    drive_file_id TEXT,
                    start_date TEXT,
                    completion_date TEXT,
                    project_site TEXT,
                    subcontractors TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'draft',
                    adobe_agreement_id TEXT,
                    adobe_agreement_status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS change_orders (
                    id SERIAL PRIMARY KEY,
                    contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
                    change_order_number TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    line_items TEXT DEFAULT '[]',
                    price_delta REAL DEFAULT 0,
                    days_delta INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    pdf_path TEXT,
                    drive_file_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS adobe_tokens (
                    id SERIAL PRIMARY KEY,
                    access_token TEXT,
                    refresh_token TEXT,
                    expires_at TEXT,
                    api_access_point TEXT
                )""",
            ]
            with self._conn() as conn:
                cur = conn.cursor()
                for stmt in statements:
                    cur.execute(stmt)
        else:
            with self._conn() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        property_address TEXT NOT NULL,
                        customer_name TEXT NOT NULL,
                        customer_phone TEXT,
                        customer_email TEXT,
                        project_type TEXT,
                        start_date TEXT,
                        end_date TEXT,
                        duration_days INTEGER DEFAULT NULL,
                        status TEXT DEFAULT 'active',
                        notes TEXT DEFAULT '',
                        drive_folder_id TEXT,
                        drive_invoices_folder_id TEXT,
                        drive_estimates_folder_id TEXT,
                        created_at TEXT DEFAULT (datetime('now'))
                    );

                    CREATE TABLE IF NOT EXISTS estimates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        estimate_number TEXT NOT NULL,
                        date_issued TEXT NOT NULL,
                        valid_until TEXT NOT NULL,
                        prepared_by TEXT,
                        tax_rate REAL DEFAULT 0,
                        permit_fees REAL DEFAULT 0,
                        discount REAL DEFAULT 0,
                        status TEXT DEFAULT 'draft',
                        drive_file_id TEXT,
                        created_at TEXT DEFAULT (datetime('now'))
                    );

                    CREATE TABLE IF NOT EXISTS estimate_line_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        estimate_id INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
                        section TEXT NOT NULL,
                        line_number INTEGER NOT NULL,
                        description TEXT NOT NULL,
                        qty REAL NOT NULL DEFAULT 1,
                        unit TEXT DEFAULT 'ea',
                        unit_price REAL NOT NULL DEFAULT 0
                    );

                    CREATE TABLE IF NOT EXISTS payment_schedule (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        estimate_id INTEGER NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
                        payment_number INTEGER NOT NULL,
                        label TEXT NOT NULL,
                        description TEXT NOT NULL,
                        due_date TEXT,
                        amount REAL NOT NULL DEFAULT 0,
                        status TEXT DEFAULT 'Pending'
                    );

                    CREATE TABLE IF NOT EXISTS invoices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        estimate_id INTEGER REFERENCES estimates(id),
                        invoice_number TEXT NOT NULL,
                        stripe_invoice_id TEXT,
                        stripe_invoice_url TEXT,
                        customer_name TEXT NOT NULL,
                        customer_email TEXT NOT NULL,
                        description TEXT,
                        amount REAL NOT NULL DEFAULT 0,
                        tax_amount REAL DEFAULT 0,
                        date_issued TEXT,
                        due_date TEXT,
                        status TEXT DEFAULT 'draft',
                        payment_date TEXT,
                        notes TEXT DEFAULT '',
                        drive_file_id TEXT,
                        created_at TEXT DEFAULT (datetime('now'))
                    );

                    CREATE TABLE IF NOT EXISTS contracts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        estimate_id INTEGER REFERENCES estimates(id),
                        contract_number TEXT NOT NULL,
                        pdf_path TEXT,
                        drive_file_id TEXT,
                        start_date TEXT,
                        completion_date TEXT,
                        project_site TEXT,
                        subcontractors TEXT DEFAULT '[]',
                        status TEXT DEFAULT 'draft',
                        adobe_agreement_id TEXT,
                        adobe_agreement_status TEXT,
                        created_at TEXT DEFAULT (datetime('now'))
                    );

                    CREATE TABLE IF NOT EXISTS change_orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
                        change_order_number TEXT NOT NULL,
                        description TEXT DEFAULT '',
                        line_items TEXT DEFAULT '[]',
                        price_delta REAL DEFAULT 0,
                        days_delta INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'draft',
                        pdf_path TEXT,
                        drive_file_id TEXT,
                        created_at TEXT DEFAULT (datetime('now'))
                    );

                    CREATE TABLE IF NOT EXISTS adobe_tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        access_token TEXT,
                        refresh_token TEXT,
                        expires_at TEXT,
                        api_access_point TEXT
                    );
                """)

    def _migrate(self):
        """Add columns that didn't exist in earlier schema versions."""
        migrations = [
            "ALTER TABLE projects ADD COLUMN duration_days INTEGER DEFAULT NULL",
            "ALTER TABLE invoices ADD COLUMN stripe_invoice_number TEXT DEFAULT NULL",
            "ALTER TABLE estimates ADD COLUMN source_pdf_path TEXT DEFAULT NULL",
        ]
        with self._conn() as conn:
            cur = conn.cursor()
            for sql in migrations:
                try:
                    cur.execute(sql)
                    conn.commit()
                except Exception:
                    # Column already exists — on Postgres a failed statement
                    # aborts the transaction, so every later statement on this
                    # connection would silently fail too unless we roll back
                    # here before moving on to the next migration.
                    conn.rollback()

    # ── Projects ─────────────────────────────────────────────────────────────

    def create_project(self, p: Project) -> int:
        sql = self._q(
            """INSERT INTO projects
               (name, property_address, customer_name, customer_phone, customer_email,
                project_type, start_date, end_date, duration_days, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)"""
            + (" RETURNING id" if self._is_pg else "")
        )
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, (p.name, p.property_address, p.customer_name, p.customer_phone,
                              p.customer_email, p.project_type,
                              p.start_date.isoformat() if p.start_date else None,
                              p.end_date.isoformat() if p.end_date else None,
                              p.duration_days, p.status, p.notes))
            return self._lastid(cur)

    def update_project_drive_folders(self, project_id: int, folder_id: str,
                                     invoices_id: str, estimates_id: str):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("""UPDATE projects SET drive_folder_id=?, drive_invoices_folder_id=?,
                   drive_estimates_folder_id=? WHERE id=?"""),
                (folder_id, invoices_id, estimates_id, project_id),
            )

    def get_project(self, project_id: int) -> Optional[Project]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q("SELECT * FROM projects WHERE id=?"), (project_id,))
            row = cur.fetchone()
            return self._row_to_project(row) if row else None

    def list_projects(self) -> List[Project]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM projects ORDER BY created_at DESC")
            return [self._row_to_project(r) for r in cur.fetchall()]

    def update_project_status(self, project_id: int, status: str):
        with self._conn() as conn:
            conn.cursor().execute(self._q("UPDATE projects SET status=? WHERE id=?"),
                                  (status, project_id))

    def update_project(self, project_id: int, name: str, property_address: str,
                       customer_name: str, customer_phone: str, customer_email: str,
                       project_type: str, notes: str,
                       start_date: str = "", duration_days: int = None):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("""UPDATE projects SET name=?, property_address=?, customer_name=?,
                   customer_phone=?, customer_email=?, project_type=?, notes=?,
                   start_date=?, duration_days=? WHERE id=?"""),
                (name, property_address, customer_name, customer_phone,
                 customer_email, project_type, notes,
                 start_date or None, duration_days, project_id),
            )

    def delete_project(self, project_id: int):
        with self._conn() as conn:
            conn.cursor().execute(self._q("DELETE FROM projects WHERE id=?"), (project_id,))

    def _row_to_project(self, row) -> Project:
        return Project(
            id=row["id"], name=row["name"], property_address=row["property_address"],
            customer_name=row["customer_name"], customer_phone=row["customer_phone"],
            customer_email=row["customer_email"], project_type=row["project_type"],
            start_date=date.fromisoformat(row["start_date"]) if row["start_date"] else None,
            end_date=date.fromisoformat(row["end_date"]) if row["end_date"] else None,
            duration_days=row["duration_days"],
            status=row["status"], notes=row["notes"],
            drive_folder_id=row["drive_folder_id"],
            drive_invoices_folder_id=row["drive_invoices_folder_id"],
            drive_estimates_folder_id=row["drive_estimates_folder_id"],
            created_at=row["created_at"],
        )

    # ── Estimates ─────────────────────────────────────────────────────────────

    def create_estimate(self, est: Estimate) -> int:
        ins_est = self._q(
            """INSERT INTO estimates
               (project_id, estimate_number, date_issued, valid_until, prepared_by,
                tax_rate, permit_fees, discount, status, source_pdf_path)
               VALUES (?,?,?,?,?,?,?,?,?,?)"""
            + (" RETURNING id" if self._is_pg else "")
        )
        ins_item = self._q(
            """INSERT INTO estimate_line_items
               (estimate_id, section, line_number, description, qty, unit, unit_price)
               VALUES (?,?,?,?,?,?,?)"""
        )
        ins_ps = self._q(
            """INSERT INTO payment_schedule
               (estimate_id, payment_number, label, description, due_date, amount, status)
               VALUES (?,?,?,?,?,?,?)"""
        )
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(ins_est, (est.project_id, est.estimate_number,
                                  est.date_issued.isoformat(), est.valid_until.isoformat(),
                                  est.prepared_by, est.tax_rate, est.permit_fees,
                                  est.discount, est.status, est.source_pdf_path))
            est_id = self._lastid(cur)
            for item in est.line_items:
                cur.execute(ins_item, (est_id, item.section, item.line_number,
                                       item.description, item.qty, item.unit, item.unit_price))
            for ps in est.payment_schedule:
                cur.execute(ins_ps, (est_id, ps.payment_number, ps.label, ps.description,
                                     ps.due_date.isoformat() if ps.due_date else None,
                                     ps.amount, ps.status))
            return est_id

    def get_estimate(self, estimate_id: int) -> Optional[Estimate]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q("SELECT * FROM estimates WHERE id=?"), (estimate_id,))
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(self._q("SELECT * FROM estimate_line_items WHERE estimate_id=? ORDER BY line_number"), (estimate_id,))
            items = cur.fetchall()
            cur.execute(self._q("SELECT * FROM payment_schedule WHERE estimate_id=? ORDER BY payment_number"), (estimate_id,))
            schedule = cur.fetchall()
            return self._row_to_estimate(row, items, schedule)

    def list_estimates(self, project_id: int) -> List[Estimate]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q("SELECT * FROM estimates WHERE project_id=? ORDER BY created_at DESC"), (project_id,))
            rows = cur.fetchall()
            result = []
            for row in rows:
                cur.execute(self._q("SELECT * FROM estimate_line_items WHERE estimate_id=? ORDER BY line_number"), (row["id"],))
                items = cur.fetchall()
                cur.execute(self._q("SELECT * FROM payment_schedule WHERE estimate_id=? ORDER BY payment_number"), (row["id"],))
                schedule = cur.fetchall()
                result.append(self._row_to_estimate(row, items, schedule))
            return result

    def delete_estimate(self, estimate_id: int):
        with self._conn() as conn:
            conn.cursor().execute(self._q("DELETE FROM estimates WHERE id=?"), (estimate_id,))

    def update_estimate(self, est: Estimate):
        """Replace all line items and payment schedule; update pricing fields."""
        upd = self._q(
            "UPDATE estimates SET tax_rate=?, permit_fees=?, discount=? WHERE id=?")
        del_items = self._q("DELETE FROM estimate_line_items WHERE estimate_id=?")
        del_ps    = self._q("DELETE FROM payment_schedule WHERE estimate_id=?")
        ins_item  = self._q(
            """INSERT INTO estimate_line_items
               (estimate_id, section, line_number, description, qty, unit, unit_price)
               VALUES (?,?,?,?,?,?,?)""")
        ins_ps    = self._q(
            """INSERT INTO payment_schedule
               (estimate_id, payment_number, label, description, due_date, amount, status)
               VALUES (?,?,?,?,?,?,?)""")
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(upd, (est.tax_rate, est.permit_fees, est.discount, est.id))
            cur.execute(del_items, (est.id,))
            cur.execute(del_ps, (est.id,))
            for item in est.line_items:
                cur.execute(ins_item, (est.id, item.section, item.line_number,
                                       item.description, item.qty, item.unit, item.unit_price))
            for ps in est.payment_schedule:
                cur.execute(ins_ps, (est.id, ps.payment_number, ps.label, ps.description,
                                     ps.due_date.isoformat() if ps.due_date else None,
                                     ps.amount, ps.status))

    def update_estimate_drive_file(self, estimate_id: int, file_id: str):
        with self._conn() as conn:
            conn.cursor().execute(self._q("UPDATE estimates SET drive_file_id=? WHERE id=?"), (file_id, estimate_id))

    def update_estimate_status(self, estimate_id: int, status: str):
        with self._conn() as conn:
            conn.cursor().execute(self._q("UPDATE estimates SET status=? WHERE id=?"), (status, estimate_id))

    def _row_to_estimate(self, row, item_rows, schedule_rows) -> Estimate:
        items = [
            EstimateLineItem(
                id=r["id"], estimate_id=r["estimate_id"], section=r["section"],
                line_number=r["line_number"], description=r["description"],
                qty=r["qty"], unit=r["unit"], unit_price=r["unit_price"],
            )
            for r in item_rows
        ]
        schedule = [
            PaymentScheduleItem(
                id=r["id"], estimate_id=r["estimate_id"],
                payment_number=r["payment_number"], label=r["label"],
                description=r["description"],
                due_date=date.fromisoformat(r["due_date"]) if r["due_date"] else None,
                amount=r["amount"], status=r["status"],
            )
            for r in schedule_rows
        ]
        return Estimate(
            id=row["id"], project_id=row["project_id"],
            estimate_number=row["estimate_number"],
            date_issued=date.fromisoformat(row["date_issued"]),
            valid_until=date.fromisoformat(row["valid_until"]),
            prepared_by=row["prepared_by"],
            tax_rate=row["tax_rate"], permit_fees=row["permit_fees"],
            discount=row["discount"], status=row["status"],
            line_items=items, payment_schedule=schedule,
            drive_file_id=row["drive_file_id"],
            source_pdf_path=row["source_pdf_path"] if "source_pdf_path" in row.keys() else None,
            created_at=row["created_at"],
        )

    # ── Invoices ──────────────────────────────────────────────────────────────

    def create_invoice(self, inv: Invoice) -> int:
        sql = self._q(
            """INSERT INTO invoices
               (project_id, estimate_id, invoice_number, stripe_invoice_id,
                stripe_invoice_url, customer_name, customer_email, description,
                amount, tax_amount, date_issued, due_date, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
            + (" RETURNING id" if self._is_pg else "")
        )
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, (inv.project_id, inv.estimate_id, inv.invoice_number,
                              inv.stripe_invoice_id, inv.stripe_invoice_url,
                              inv.customer_name, inv.customer_email, inv.description,
                              inv.amount, inv.tax_amount,
                              inv.date_issued.isoformat() if inv.date_issued else None,
                              inv.due_date.isoformat() if inv.due_date else None,
                              inv.status, inv.notes))
            return self._lastid(cur)

    def get_invoice(self, invoice_id: int) -> Optional[Invoice]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q("SELECT * FROM invoices WHERE id=?"), (invoice_id,))
            row = cur.fetchone()
            return self._row_to_invoice(row) if row else None

    def list_invoices(self, project_id: int) -> List[Invoice]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q("SELECT * FROM invoices WHERE project_id=? ORDER BY created_at DESC"), (project_id,))
            return [self._row_to_invoice(r) for r in cur.fetchall()]

    def update_invoice_stripe(self, invoice_id: int, stripe_id: str, stripe_url: str,
                               status: str, stripe_invoice_number: str = ""):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("""UPDATE invoices
                           SET stripe_invoice_id=?, stripe_invoice_url=?,
                               status=?, stripe_invoice_number=?
                           WHERE id=?"""),
                (stripe_id, stripe_url, status, stripe_invoice_number or None, invoice_id),
            )

    def update_invoice_status(self, invoice_id: int, status: str, payment_date: Optional[str] = None):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("UPDATE invoices SET status=?, payment_date=? WHERE id=?"),
                (status, payment_date, invoice_id),
            )

    def update_invoice(self, invoice_id: int, description: str, amount: float,
                       tax_amount: float, due_date: Optional[str], notes: str,
                       estimate_id: Optional[int] = None):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("""UPDATE invoices SET description=?, amount=?, tax_amount=?,
                   due_date=?, notes=?, estimate_id=? WHERE id=?"""),
                (description, amount, tax_amount, due_date, notes, estimate_id, invoice_id),
            )

    def delete_invoice(self, invoice_id: int):
        with self._conn() as conn:
            conn.cursor().execute(self._q("DELETE FROM invoices WHERE id=?"), (invoice_id,))

    def update_invoice_drive_file(self, invoice_id: int, file_id: str):
        with self._conn() as conn:
            conn.cursor().execute(self._q("UPDATE invoices SET drive_file_id=? WHERE id=?"), (file_id, invoice_id))

    def _row_to_invoice(self, row) -> Invoice:
        return Invoice(
            id=row["id"], project_id=row["project_id"], estimate_id=row["estimate_id"],
            invoice_number=row["invoice_number"], stripe_invoice_id=row["stripe_invoice_id"],
            stripe_invoice_url=row["stripe_invoice_url"],
            stripe_invoice_number=row["stripe_invoice_number"] if "stripe_invoice_number" in row.keys() else None,
            customer_name=row["customer_name"], customer_email=row["customer_email"],
            description=row["description"], amount=row["amount"], tax_amount=row["tax_amount"],
            date_issued=date.fromisoformat(row["date_issued"]) if row["date_issued"] else None,
            due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
            status=row["status"],
            payment_date=date.fromisoformat(row["payment_date"]) if row["payment_date"] else None,
            notes=row["notes"], drive_file_id=row["drive_file_id"], created_at=row["created_at"],
        )

    # ── Contracts ────────────────────────────────────────────────────────────

    def create_contract(self, c: Contract) -> int:
        sql = self._q(
            """INSERT INTO contracts
               (project_id, estimate_id, contract_number, pdf_path, drive_file_id,
                start_date, completion_date, project_site, subcontractors, status)
               VALUES (?,?,?,?,?,?,?,?,?,?)"""
            + (" RETURNING id" if self._is_pg else "")
        )
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, (c.project_id, c.estimate_id, c.contract_number, c.pdf_path,
                              c.drive_file_id, c.start_date, c.completion_date, c.project_site,
                              json.dumps(c.subcontractors or []), c.status))
            return self._lastid(cur)

    def get_contract(self, contract_id: int) -> Optional[Contract]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q("SELECT * FROM contracts WHERE id=?"), (contract_id,))
            row = cur.fetchone()
            return self._row_to_contract(row) if row else None

    def get_contract_by_project(self, project_id: int) -> Optional[Contract]:
        """Most recently created contract for a project, or None if none exists yet."""
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q(
                "SELECT * FROM contracts WHERE project_id=? ORDER BY id DESC"), (project_id,))
            row = cur.fetchone()
            return self._row_to_contract(row) if row else None

    def list_contracts(self, project_id: int) -> List[Contract]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q(
                "SELECT * FROM contracts WHERE project_id=? ORDER BY id DESC"), (project_id,))
            return [self._row_to_contract(r) for r in cur.fetchall()]

    def update_contract_pdf(self, contract_id: int, pdf_path: str, drive_file_id: Optional[str] = None):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("UPDATE contracts SET pdf_path=?, drive_file_id=? WHERE id=?"),
                (pdf_path, drive_file_id, contract_id),
            )

    def update_contract(self, contract_id: int, estimate_id: Optional[int], pdf_path: str,
                         drive_file_id: Optional[str], start_date: Optional[str],
                         completion_date: Optional[str], project_site: Optional[str],
                         subcontractors: list):
        """Full-field update, used when re-generating a still-draft contract in place."""
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("""UPDATE contracts SET estimate_id=?, pdf_path=?, drive_file_id=?,
                   start_date=?, completion_date=?, project_site=?, subcontractors=?
                   WHERE id=?"""),
                (estimate_id, pdf_path, drive_file_id, start_date, completion_date,
                 project_site, json.dumps(subcontractors or []), contract_id),
            )

    def update_contract_adobe_status(self, contract_id: int, status: str,
                                      adobe_agreement_id: Optional[str] = None,
                                      adobe_agreement_status: Optional[str] = None):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("""UPDATE contracts
                           SET status=?,
                               adobe_agreement_id=COALESCE(?, adobe_agreement_id),
                               adobe_agreement_status=?
                           WHERE id=?"""),
                (status, adobe_agreement_id, adobe_agreement_status, contract_id),
            )

    def _row_to_contract(self, row) -> Contract:
        return Contract(
            id=row["id"], project_id=row["project_id"], estimate_id=row["estimate_id"],
            contract_number=row["contract_number"], pdf_path=row["pdf_path"],
            drive_file_id=row["drive_file_id"], start_date=row["start_date"],
            completion_date=row["completion_date"], project_site=row["project_site"],
            subcontractors=json.loads(row["subcontractors"] or "[]"),
            status=row["status"], adobe_agreement_id=row["adobe_agreement_id"],
            adobe_agreement_status=row["adobe_agreement_status"], created_at=row["created_at"],
        )

    # ── Change Orders ────────────────────────────────────────────────────────

    def create_change_order(self, co: ChangeOrder) -> int:
        sql = self._q(
            """INSERT INTO change_orders
               (contract_id, change_order_number, description, line_items,
                price_delta, days_delta, status, pdf_path, drive_file_id)
               VALUES (?,?,?,?,?,?,?,?,?)"""
            + (" RETURNING id" if self._is_pg else "")
        )
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, (co.contract_id, co.change_order_number, co.description,
                              json.dumps(co.line_items or []), co.price_delta, co.days_delta,
                              co.status, co.pdf_path, co.drive_file_id))
            return self._lastid(cur)

    def list_change_orders(self, contract_id: int) -> List[ChangeOrder]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q(
                "SELECT * FROM change_orders WHERE contract_id=? ORDER BY created_at DESC"),
                (contract_id,))
            return [self._row_to_change_order(r) for r in cur.fetchall()]

    def _row_to_change_order(self, row) -> ChangeOrder:
        return ChangeOrder(
            id=row["id"], contract_id=row["contract_id"],
            change_order_number=row["change_order_number"], description=row["description"],
            line_items=json.loads(row["line_items"] or "[]"),
            price_delta=row["price_delta"], days_delta=row["days_delta"],
            status=row["status"], pdf_path=row["pdf_path"], drive_file_id=row["drive_file_id"],
            created_at=row["created_at"],
        )

    # ── Adobe Tokens ─────────────────────────────────────────────────────────
    # Single-tenant app (one Adobe Acrobat Sign account for Cabrera Construction),
    # so a single stored token row is sufficient — no per-user token table.

    def get_adobe_token(self) -> Optional[dict]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM adobe_tokens ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None
            return {"access_token": row["access_token"], "refresh_token": row["refresh_token"],
                    "expires_at": row["expires_at"], "api_access_point": row["api_access_point"]}

    def save_adobe_token(self, access_token: str, refresh_token: str, expires_at: str,
                          api_access_point: str):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM adobe_tokens")
            cur.execute(
                self._q("INSERT INTO adobe_tokens "
                        "(access_token, refresh_token, expires_at, api_access_point) "
                        "VALUES (?,?,?,?)"),
                (access_token, refresh_token, expires_at, api_access_point),
            )
