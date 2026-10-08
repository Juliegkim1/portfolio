import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { dateTimeFmt } from "../format";

export function DriveFilePickerDialog({
  onClose,
  onPick,
  picking,
}: {
  onClose: () => void;
  onPick: (fileId: string, fileName: string) => void;
  // True while the picked file is being downloaded + extracted — keeps the
  // dialog open with a loading state instead of closing immediately, since
  // that extraction can take a little while (see gemini_service's bounded
  // retry budget).
  picking: boolean;
}) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const query = useQuery({
    queryKey: ["drive-documents", debouncedSearch],
    queryFn: () => api.drive.searchDocuments(debouncedSearch),
  });

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-title">{t("drivePicker.title")}</div>
        <input
          className="input"
          placeholder={t("drivePicker.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
        />
        <div className="muted" style={{ fontSize: 12, marginTop: "var(--space-1)" }}>
          {t("drivePicker.formatsNote")}
        </div>

        <div className="stack" style={{ marginTop: "var(--space-3)", maxHeight: 320, overflowY: "auto" }}>
          {query.isLoading ? (
            <div className="loading-state">{t("drivePicker.searching")}</div>
          ) : query.isError ? (
            <div className="error-state">{(query.error as Error).message}</div>
          ) : query.data && query.data.length > 0 ? (
            query.data.map((f) => (
              <div
                key={f.id}
                className="card row-between"
                role="button"
                tabIndex={0}
                style={{ padding: "var(--space-3)", cursor: picking ? "default" : "pointer", opacity: picking ? 0.6 : 1 }}
                onClick={() => !picking && onPick(f.id, f.name)}
                onKeyDown={(e) => e.key === "Enter" && !picking && onPick(f.id, f.name)}
              >
                <div className="icon-text">
                  <FileText size={16} strokeWidth={1.5} />
                  <span>{f.name}</span>
                </div>
                <span className="muted" style={{ fontSize: 12 }}>
                  {dateTimeFmt(f.modified_time)}
                </span>
              </div>
            ))
          ) : (
            <div className="empty-state">
              {debouncedSearch ? t("drivePicker.noFilesMatching", { search: debouncedSearch }) : t("drivePicker.noFilesInDrive")}
            </div>
          )}
        </div>

        {picking && <div className="loading-state">{t("estimateUpload.readingDocument")}</div>}

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={picking}>
            {t("common.cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
