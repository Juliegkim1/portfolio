import { useQuery } from "@tanstack/react-query";
import React from "react";
import { api } from "../api/client";
import { MobileHeader, MobileTabBar } from "./MobileShell";
import { Sidebar } from "./Sidebar";

export function AppShell({
  title,
  context,
  actions,
  children,
}: {
  title: string;
  context?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const { data: status } = useQuery({ queryKey: ["integrations-status"], queryFn: api.integrationsStatus });

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main">
        <MobileHeader title={title} />
        <header className="topbar desktop-only">
          <div>
            <h2>{title}</h2>
            {context && <div className="topbar-context">{context}</div>}
          </div>
          <div className="topbar-tags">
            <span className="tag tag-outline">QuickBooks · {status?.quickbooks ? "Connected" : "Disconnected"}</span>
            <span className="tag tag-outline">Adobe Acrobat · {status?.adobe_sign ? "Connected" : "Disconnected"}</span>
            <span className="tag tag-outline">Google Workspace · {status?.google_workspace ? "Connected" : "Disconnected"}</span>
          </div>
        </header>
        <main className="content">
          {actions && <div className="page-header-actions desktop-only" style={{ marginBottom: "var(--space-4)" }}>{actions}</div>}
          {children}
        </main>
        <MobileTabBar />
      </div>
    </div>
  );
}
