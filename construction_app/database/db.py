import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import List, Optional

from config import DATABASE_URL
from models import Project, Estimate, EstimateLineItem, PaymentScheduleItem, Invoice, WorkBreakdownItem


class Database:
    def __init__(self, db_path: str = DATABASE_URL):
        self.db_path = db_path
        self._init_schema()

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
            return cursor.fetchone()[0]
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
                """CREATE TABLE IF NOT EXISTS work_breakdown (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    phase TEXT NOT NULL,
                    task TEXT NOT NULL,
                    assigned_to TEXT DEFAULT '',
                    estimated_hours REAL DEFAULT 0,
                    actual_hours REAL DEFAULT 0,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'not_started',
                    notes TEXT DEFAULT ''
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

                    CREATE TABLE IF NOT EXISTS work_breakdown (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                        phase TEXT NOT NULL,
                        task TEXT NOT NULL,
                        assigned_to TEXT DEFAULT '',
                        estimated_hours REAL DEFAULT 0,
                        actual_hours REAL DEFAULT 0,
                        start_date TEXT,
                        end_date TEXT,
                        status TEXT DEFAULT 'not_started',
                        notes TEXT DEFAULT ''
                    );
                """)

    # ── Projects ─────────────────────────────────────────────────────────────

    def create_project(self, p: Project) -> int:
        sql = self._q(
            """INSERT INTO projects
               (name, property_address, customer_name, customer_phone, customer_email,
                project_type, start_date, end_date, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)"""
            + (" RETURNING id" if self._is_pg else "")
        )
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, (p.name, p.property_address, p.customer_name, p.customer_phone,
                              p.customer_email, p.project_type,
                              p.start_date.isoformat() if p.start_date else None,
                              p.end_date.isoformat() if p.end_date else None,
                              p.status, p.notes))
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
                       project_type: str, notes: str):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("""UPDATE projects SET name=?, property_address=?, customer_name=?,
                   customer_phone=?, customer_email=?, project_type=?, notes=? WHERE id=?"""),
                (name, property_address, customer_name, customer_phone,
                 customer_email, project_type, notes, project_id),
            )

    def _row_to_project(self, row) -> Project:
        return Project(
            id=row["id"], name=row["name"], property_address=row["property_address"],
            customer_name=row["customer_name"], customer_phone=row["customer_phone"],
            customer_email=row["customer_email"], project_type=row["project_type"],
            start_date=date.fromisoformat(row["start_date"]) if row["start_date"] else None,
            end_date=date.fromisoformat(row["end_date"]) if row["end_date"] else None,
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
                tax_rate, permit_fees, discount, status)
               VALUES (?,?,?,?,?,?,?,?,?)"""
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
                                  est.discount, est.status))
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
            drive_file_id=row["drive_file_id"], created_at=row["created_at"],
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

    def update_invoice_stripe(self, invoice_id: int, stripe_id: str, stripe_url: str, status: str):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("UPDATE invoices SET stripe_invoice_id=?, stripe_invoice_url=?, status=? WHERE id=?"),
                (stripe_id, stripe_url, status, invoice_id),
            )

    def update_invoice_status(self, invoice_id: int, status: str, payment_date: Optional[str] = None):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("UPDATE invoices SET status=?, payment_date=? WHERE id=?"),
                (status, payment_date, invoice_id),
            )

    def update_invoice(self, invoice_id: int, description: str, amount: float,
                       tax_amount: float, due_date: Optional[str], notes: str):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("""UPDATE invoices SET description=?, amount=?, tax_amount=?,
                   due_date=?, notes=? WHERE id=?"""),
                (description, amount, tax_amount, due_date, notes, invoice_id),
            )

    def update_invoice_drive_file(self, invoice_id: int, file_id: str):
        with self._conn() as conn:
            conn.cursor().execute(self._q("UPDATE invoices SET drive_file_id=? WHERE id=?"), (file_id, invoice_id))

    def _row_to_invoice(self, row) -> Invoice:
        return Invoice(
            id=row["id"], project_id=row["project_id"], estimate_id=row["estimate_id"],
            invoice_number=row["invoice_number"], stripe_invoice_id=row["stripe_invoice_id"],
            stripe_invoice_url=row["stripe_invoice_url"],
            customer_name=row["customer_name"], customer_email=row["customer_email"],
            description=row["description"], amount=row["amount"], tax_amount=row["tax_amount"],
            date_issued=date.fromisoformat(row["date_issued"]) if row["date_issued"] else None,
            due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
            status=row["status"],
            payment_date=date.fromisoformat(row["payment_date"]) if row["payment_date"] else None,
            notes=row["notes"], drive_file_id=row["drive_file_id"], created_at=row["created_at"],
        )

    # ── Work Breakdown ────────────────────────────────────────────────────────

    def create_wbs_item(self, item: WorkBreakdownItem) -> int:
        sql = self._q(
            """INSERT INTO work_breakdown
               (project_id, phase, task, assigned_to, estimated_hours,
                actual_hours, start_date, end_date, status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)"""
            + (" RETURNING id" if self._is_pg else "")
        )
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, (item.project_id, item.phase, item.task, item.assigned_to,
                              item.estimated_hours, item.actual_hours,
                              item.start_date, item.end_date, item.status, item.notes))
            return self._lastid(cur)

    def list_wbs(self, project_id: int) -> List[WorkBreakdownItem]:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(self._q("SELECT * FROM work_breakdown WHERE project_id=? ORDER BY phase, id"), (project_id,))
            return [
                WorkBreakdownItem(
                    id=r["id"], project_id=r["project_id"], phase=r["phase"],
                    task=r["task"], assigned_to=r["assigned_to"],
                    estimated_hours=r["estimated_hours"], actual_hours=r["actual_hours"],
                    start_date=r["start_date"], end_date=r["end_date"],
                    status=r["status"], notes=r["notes"],
                )
                for r in cur.fetchall()
            ]

    def update_wbs_status(self, item_id: int, status: str, actual_hours: float = None):
        with self._conn() as conn:
            cur = conn.cursor()
            if actual_hours is not None:
                cur.execute(self._q("UPDATE work_breakdown SET status=?, actual_hours=? WHERE id=?"),
                            (status, actual_hours, item_id))
            else:
                cur.execute(self._q("UPDATE work_breakdown SET status=? WHERE id=?"), (status, item_id))

    def update_wbs_item(self, item_id: int, phase: str, task: str, assigned_to: str,
                        estimated_hours: float, start_date: Optional[str], end_date: Optional[str]):
        with self._conn() as conn:
            conn.cursor().execute(
                self._q("""UPDATE work_breakdown SET phase=?, task=?, assigned_to=?,
                   estimated_hours=?, start_date=?, end_date=? WHERE id=?"""),
                (phase, task, assigned_to, estimated_hours, start_date, end_date, item_id),
            )

    def delete_wbs_item(self, item_id: int):
        with self._conn() as conn:
            conn.cursor().execute(self._q("DELETE FROM work_breakdown WHERE id=?"), (item_id,))
