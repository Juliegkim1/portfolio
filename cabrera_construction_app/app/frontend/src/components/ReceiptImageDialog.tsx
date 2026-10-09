import { useTranslation } from "react-i18next";
import { api } from "../api/client";

// Shows the original Drive photo for a receipt synced from My
// Drive/Receipts — lets the owner look at it to identify/correct a
// receipt sync_receipts_from_drive couldn't confidently match on its own,
// without needing to open Drive separately.
export function ReceiptImageDialog({ driveFileId, description, onClose }: { driveFileId: string; description: string; onClose: () => void }) {
  const { t } = useTranslation();

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-title">{description}</div>
        <img
          src={api.drive.fileContentUrl(driveFileId)}
          alt={description}
          style={{ maxWidth: "100%", maxHeight: "70vh", display: "block", margin: "0 auto", borderRadius: "var(--radius-md, 6px)" }}
        />
        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
