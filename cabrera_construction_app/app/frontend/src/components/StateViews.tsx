import { ApiError } from "../api/client";

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return <div className="loading-state">{label}</div>;
}

export function EmptyState({ label }: { label: string }) {
  return <div className="empty-state">{label}</div>;
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Something went wrong.";
  return <div className="error-state">{message}</div>;
}

export function StatusTag({ status }: { status: string }) {
  const variant =
    status === "paid" || status === "active" || status === "signed" || status === "matched" || status === "completed"
      ? "tag-accent"
      : status === "scheduled" || status === "possible"
        ? "tag-neutral"
        : "tag-outline";
  return <span className={`tag ${variant}`}>{status.replace(/_/g, " ")}</span>;
}
