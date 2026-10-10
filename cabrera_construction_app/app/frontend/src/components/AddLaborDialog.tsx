import { useState } from "react";
import { useTranslation } from "react-i18next";

// Actual labor cost for the current project -- person, date, amount.
// Always tied to the project the Reconciliation page is already showing,
// so unlike AddReceiptDialog there's no project picker here.
export function AddLaborDialog({
  onClose,
  onSave,
  saving,
  error,
}: {
  onClose: () => void;
  onSave: (payload: { person_name: string; date: string; amount: number }) => void;
  saving: boolean;
  error?: string | null;
}) {
  const { t } = useTranslation();
  const [personName, setPersonName] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [amount, setAmount] = useState("");

  const canSubmit = personName.trim() !== "" && Number(amount) > 0;

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-title">{t("reconciliation.addLabor")}</div>

        <div className="field">
          <label>{t("reconciliation.person")}</label>
          <input className="input" value={personName} onChange={(e) => setPersonName(e.target.value)} autoFocus />
        </div>

        <div className="field">
          <label>{t("common.date")}</label>
          <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        <div className="field">
          <label>{t("common.amount")}</label>
          <input className="input" type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>

        {error && <div className="error-state">{error}</div>}

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose} disabled={saving}>
            {t("common.cancel")}
          </button>
          <button
            className="btn btn-primary"
            disabled={!canSubmit || saving}
            onClick={() => onSave({ person_name: personName.trim(), date, amount: Number(amount) })}
          >
            {t("common.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
