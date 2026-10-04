import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import type { UserRole } from "../api/types";
import { AppShell } from "../components/AppShell";
import { LoadingState, StatusTag } from "../components/StateViews";
import { dateTimeFmt } from "../format";

export function TeamUsersPage() {
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

  return (
    <AppShell title="Team & Users">
      <div className="page-header">
        <div />
        <div className="page-header-actions">
          <button className="btn btn-primary" onClick={() => setShowInvite(true)}>
            <Plus size={14} strokeWidth={1.5} /> Invite User
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
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last Active</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {query.data?.map((u) => (
                <tr key={u.id}>
                  <td>{u.name}</td>
                  <td className="muted">{u.email}</td>
                  <td>{u.role === "owner" ? "Owner / Admin" : "Project Manager"}</td>
                  <td>
                    <StatusTag status={u.status} />
                  </td>
                  <td className="muted">{dateTimeFmt(u.last_active_at)}</td>
                  <td>
                    <div className="row">
                      {u.status === "invited" && (
                        <button className="btn btn-ghost" disabled={resendMutation.isPending} onClick={() => resendMutation.mutate(u.id)}>
                          Resend
                        </button>
                      )}
                      <button className="btn btn-ghost" disabled={removeMutation.isPending} onClick={() => removeMutation.mutate(u.id)}>
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showInvite && (
        <div className="dialog-backdrop" onClick={() => setShowInvite(false)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <div className="dialog-title">Invite User</div>
            <div className="field">
              <label>Name</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="field">
              <label>Email</label>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              {email && !validEmail && <div className="muted" style={{ fontSize: 11, color: "#b4432f" }}>Enter a valid email address</div>}
            </div>
            <div className="field">
              <label>Role</label>
              <div className="seg">
                <label className="seg-opt">
                  <input type="radio" checked={role === "owner"} onChange={() => setRole("owner")} />
                  Owner / Admin
                </label>
                <label className="seg-opt">
                  <input type="radio" checked={role === "project_manager"} onChange={() => setRole("project_manager")} />
                  Project Manager
                </label>
              </div>
            </div>
            {inviteMutation.isError && <div className="error-state">{(inviteMutation.error as Error).message}</div>}
            <div className="dialog-actions">
              <button className="btn btn-secondary" onClick={() => setShowInvite(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" disabled={!canInvite || inviteMutation.isPending} onClick={() => inviteMutation.mutate()}>
                Send Invite
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
