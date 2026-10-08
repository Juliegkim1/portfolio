import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { UserRole } from "../api/types";
import { AppShell } from "../components/AppShell";
import { LoadingState, StatusTag } from "../components/StateViews";
import { setAppLanguage, type AppLanguage } from "../i18n";
import { dateTimeFmt } from "../format";

export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["users"], queryFn: api.users.list });
  const [showInvite, setShowInvite] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>("project_manager");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["users"] });
  const inviteMutation = useMutation({
    mutationFn: () => api.users.invite({ name, email, role }),
    onSuccess: () => {
      invalidate();
      setShowInvite(false);
      setName("");
      setEmail("");
    },
  });
  const resendMutation = useMutation({ mutationFn: (id: number) => api.users.resend(id), onSuccess: invalidate });
  const removeMutation = useMutation({ mutationFn: (id: number) => api.users.remove(id), onSuccess: invalidate });

  const validEmail = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email);
  const canInvite = name.trim() !== "" && validEmail;
  const currentLang = (i18n.language?.split("-")[0] as AppLanguage) || "en";

  return (
    <AppShell title={t("settings.title")} context={t("settings.context")}>
      <div className="section">
        <h3 className="icon-text">
          <Globe size={16} strokeWidth={1.5} /> {t("settings.languageSection")}
        </h3>
        <div className="card blueprint" style={{ padding: "var(--space-4)" }}>
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <div className="muted" style={{ fontSize: 13, marginBottom: "var(--space-3)" }}>
            {t("settings.languageDescription")}
          </div>
          <div className="seg">
            <label className="seg-opt">
              <input type="radio" checked={currentLang === "en"} onChange={() => setAppLanguage("en")} />
              {t("settings.languageEnglish")}
            </label>
            <label className="seg-opt">
              <input type="radio" checked={currentLang === "es"} onChange={() => setAppLanguage("es")} />
              {t("settings.languageSpanish")}
            </label>
          </div>
        </div>
      </div>

      <div className="section">
        <div className="page-header">
          <h3>{t("settings.teamSection")}</h3>
          <div className="page-header-actions">
            <button className="btn btn-primary" onClick={() => setShowInvite(true)}>
              <Plus size={14} strokeWidth={1.5} /> {t("team.inviteUser")}
            </button>
          </div>
        </div>

        {query.isLoading ? (
          <LoadingState />
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("common.name")}</th>
                  <th>{t("common.email")}</th>
                  <th>{t("team.role")}</th>
                  <th>{t("common.status")}</th>
                  <th>{t("team.lastActive")}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {query.data?.map((u) => (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td className="muted">{u.email}</td>
                    <td>{u.role === "owner" ? t("team.ownerAdmin") : t("team.projectManager")}</td>
                    <td>
                      <StatusTag status={u.status} />
                    </td>
                    <td className="muted">{dateTimeFmt(u.last_active_at)}</td>
                    <td>
                      <div className="row">
                        {u.status === "invited" && (
                          <button className="btn btn-ghost" disabled={resendMutation.isPending} onClick={() => resendMutation.mutate(u.id)}>
                            {t("team.resend")}
                          </button>
                        )}
                        <button className="btn btn-ghost" disabled={removeMutation.isPending} onClick={() => removeMutation.mutate(u.id)}>
                          {t("common.remove")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showInvite && (
        <div className="dialog-backdrop" onClick={() => setShowInvite(false)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <div className="dialog-title">{t("team.inviteUser")}</div>
            <div className="field">
              <label>{t("common.name")}</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="field">
              <label>{t("common.email")}</label>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              {email && !validEmail && (
                <div className="muted" style={{ fontSize: 11, color: "#b4432f" }}>
                  {t("team.invalidEmail")}
                </div>
              )}
            </div>
            <div className="field">
              <label>{t("team.role")}</label>
              <div className="seg">
                <label className="seg-opt">
                  <input type="radio" checked={role === "owner"} onChange={() => setRole("owner")} />
                  {t("team.ownerAdmin")}
                </label>
                <label className="seg-opt">
                  <input type="radio" checked={role === "project_manager"} onChange={() => setRole("project_manager")} />
                  {t("team.projectManager")}
                </label>
              </div>
            </div>
            {inviteMutation.isError && <div className="error-state">{(inviteMutation.error as Error).message}</div>}
            <div className="dialog-actions">
              <button className="btn btn-secondary" onClick={() => setShowInvite(false)}>
                {t("common.cancel")}
              </button>
              <button className="btn btn-primary" disabled={!canInvite || inviteMutation.isPending} onClick={() => inviteMutation.mutate()}>
                {t("team.sendInvite")}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
