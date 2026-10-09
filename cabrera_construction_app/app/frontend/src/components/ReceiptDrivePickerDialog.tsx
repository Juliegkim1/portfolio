import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { dateTimeFmt } from "../format";

// Browse/search Drive for a receipt photo directly, for when the automatic
// Receipts-inbox scan ("Sync Receipts Now") hasn't caught it -- filed
// somewhere else in Drive, synced to an unexpected folder, or the inbox
// resolution itself was briefly wrong. Mirrors DriveFilePickerDialog's
// pattern (used for picking an estimate document) but shows a photo
// thumbnail instead of a filename-only row, since recognizing the right
// receipt by sight is the whole point here.
export function ReceiptDrivePickerDialog({
  onClose,
  onPick,
  importing,
  error,
}: {
  onClose: () => void;
  onPick: (fileId: string, fileName: string) => void;
  // True while the picked photo is being read + matched — keeps the dialog
  // open with a loading state instead of closing immediately.
  importing: boolean;
  // A failed import (e.g. unreadable photo, or already imported) — shown
  // inside the dialog since it stays open, rather than as a page banner
  // that'd be hidden behind this dialog's own backdrop.
  error?: string | null;
}) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const query = useQuery({
    queryKey: ["drive-receipt-images", debouncedSearch],
    queryFn: () => api.drive.searchReceiptImages(debouncedSearch),
  });

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-title">{t("receiptDrivePicker.title")}</div>
        <input
          className="input"
          placeholder={t("receiptDrivePicker.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
        />

        <div className="stack" style={{ marginTop: "var(--space-3)", maxHeight: 360, overflowY: "auto" }}>
          {query.isLoading ? (
            <div className="loading-state">{t("receiptDrivePicker.searching")}</div>
          ) : query.isError ? (
            <div className="error-state">{(query.error as Error).message}</div>
          ) : query.data && query.data.length > 0 ? (
            query.data.map((f) => (
              <div
                key={f.id}
                className="card row-between"
                role="button"
                tabIndex={0}
                style={{ padding: "var(--space-2)", cursor: importing ? "default" : "pointer", opacity: importing ? 0.6 : 1 }}
                onClick={() => !importing && onPick(f.id, f.name)}
                onKeyDown={(e) => e.key === "Enter" && !importing && onPick(f.id, f.name)}
              >
                <div className="icon-text">
                  <img
                    src={api.drive.fileContentUrl(f.id)}
                    alt={f.name}
                    style={{ width: 40, height: 40, objectFit: "cover", borderRadius: "var(--radius-sm, 4px)" }}
                  />
                  <span>{f.name}</span>
                </div>
                <span className="muted" style={{ fontSize: 12 }}>
                  {dateTimeFmt(f.modified_time)}
                </span>
              </div>
            ))
          ) : (
            <div className="empty-state">
              {debouncedSearch ? t("receiptDrivePicker.noFilesMatching", { search: debouncedSearch }) : t("receiptDrivePicker.noFilesInDrive")}
            </div>
          )}
        </div>

        {importing && <div className="loading-state">{t("receiptDrivePicker.importing")}</div>}
        {error && <div className="error-state">{error}</div>}

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={importing}>
            {t("common.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
