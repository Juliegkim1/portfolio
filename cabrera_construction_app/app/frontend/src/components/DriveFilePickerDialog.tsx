import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { useEffect, useState } from "react";
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
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  const query = useQuery({
    queryKey: ["drive-documents", debouncedSearch],
    queryFn: () => api.drive.searchDocuments(debouncedSearch),
  });

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-title">Choose from Google Drive</div>
        <input
          className="input"
          placeholder="Search your Drive by filename…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
        />
        <div className="muted" style={{ fontSize: 12, marginTop: "var(--space-1)" }}>
          PDF and DOCX files only. Showing most recently modified first.
        </div>

        <div className="stack" style={{ marginTop: "var(--space-3)", maxHeight: 320, overflowY: "auto" }}>
          {query.isLoading ? (
            <div className="loading-state">Searching Drive…</div>
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
            <div className="empty-state">No PDF or DOCX files found{debouncedSearch ? ` matching "${debouncedSearch}"` : " in Drive"}.</div>
          )}
        </div>

        {picking && <div className="loading-state">Reading the document…</div>}

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={picking}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
