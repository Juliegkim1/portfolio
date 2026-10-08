import { useTranslation } from "react-i18next";
import { ApiError } from "../api/client";

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation();
  return <div className="loading-state">{label ?? t("common.loading")}</div>;
}

export function EmptyState({ label }: { label: string }) {
  return <div className="empty-state">{label}</div>;
}

export function ErrorState({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const message = error instanceof ApiError ? error.message : error instanceof Error ? error.message : t("common.somethingWrong");
  return <div className="error-state">{message}</div>;
}

// Status values are backend enum strings (Project.status, Invoice.status,
// etc. — see app/backend/app/schemas.py) — translated via the "status.*"
// keys when known, falling back to the raw value (spaces for underscores)
// for anything not in the dictionary rather than showing nothing.
export function StatusTag({ status }: { status: string }) {
  const { t } = useTranslation();
  const variant =
    status === "paid" || status === "active" || status === "signed" || status === "matched" || status === "completed"
      ? "tag-accent"
      : status === "scheduled" || status === "possible"
        ? "tag-neutral"
        : "tag-outline";
  return <span className={`tag ${variant}`}>{t(`status.${status}`, { defaultValue: status.replace(/_/g, " ") })}</span>;
}
