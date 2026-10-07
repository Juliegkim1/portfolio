import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState } from "../components/StateViews";
import { dateFmt, money } from "../format";

export function AnalyticsPage() {
  const [includePending, setIncludePending] = useState(false);
  const query = useQuery({ queryKey: ["analytics", includePending], queryFn: () => api.analytics.get(includePending) });

  if (query.isLoading) {
    return (
      <AppShell title="Analytics">
        <LoadingState />
      </AppShell>
    );
  }
  if (query.isError) {
    return (
      <AppShell title="Analytics">
        <ErrorState error={query.error} />
      </AppShell>
    );
  }

  const data = query.data!;
  const today = new Date();

  const allDates = data.timeline.flatMap((p) => [new Date(p.start_date), new Date(p.end_date)]);
  const minDate = allDates.length ? new Date(Math.min(...allDates.map((d) => d.getTime()))) : today;
  const maxDate = allDates.length ? new Date(Math.max(...allDates.map((d) => d.getTime()))) : today;
  const span = Math.max(1, maxDate.getTime() - minDate.getTime());
  const pct = (d: Date) => ((d.getTime() - minDate.getTime()) / span) * 100;

  const maxConcurrency = Math.max(1, ...data.concurrency.map((c) => c.count));
  const peakSet = new Set(data.peak_weeks);

  const maxRevenueMonth = Math.max(1, ...data.revenue_projection.map((r) => r.collected + r.scheduled));

  return (
    <AppShell title="Analytics" context="Company-wide performance">
      <div className="kpi-grid section">
        <div className="card">
          <div className="card-kicker">In Progress Today</div>
          <div className="kpi-value">{data.kpis.in_progress_today}</div>
        </div>
        <div className="card">
          <div className="card-kicker">Signed Contract Value</div>
          <div className="kpi-value">{money(data.kpis.signed_contract_value)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">Projected Remaining</div>
          <div className="kpi-value">{money(data.kpis.projected_remaining)}</div>
          <div className="kpi-sub">{money(data.kpis.due_next_90_days)} due in next 90 days</div>
        </div>
        <div className="card">
          <div className="card-kicker">Collected to Date</div>
          <div className="kpi-value">{money(data.kpis.collected_to_date)}</div>
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>Project Timeline</h3>
          <label className="radio">
            <input type="checkbox" checked={includePending} onChange={(e) => setIncludePending(e.target.checked)} style={{ position: "static", opacity: 1, width: "auto", height: "auto" }} />
            Include pending contracts
          </label>
        </div>
        <div className="card" style={{ padding: "var(--space-4)" }}>
          <div style={{ position: "relative" }}>
            {data.timeline.map((p) => (
              <div key={p.id} className="row" style={{ marginBottom: 10 }}>
                <div style={{ width: 160, fontSize: 12 }} className="muted">
                  {p.name}
                </div>
                <div style={{ position: "relative", flex: 1, height: 16, background: "var(--color-surface)" }}>
                  <div
                    style={{
                      position: "absolute",
                      left: `${pct(new Date(p.start_date))}%`,
                      width: `${Math.max(1, pct(new Date(p.end_date)) - pct(new Date(p.start_date)))}%`,
                      height: "100%",
                      background: p.signed ? "var(--color-accent-200)" : "transparent",
                      border: `1.5px ${p.signed ? "solid" : "dashed"} var(--color-accent-700)`,
                    }}
                  />
                </div>
              </div>
            ))}
            <div
              style={{
                position: "absolute",
                left: `calc(160px + ${pct(today)}% * (100% - 160px) / 100)`,
                top: 0,
                bottom: 0,
                width: 1,
                background: "var(--color-accent-700)",
              }}
              title="Today"
            />
          </div>
        </div>
      </div>

      <div className="section">
        <h3>Projects at the Same Time</h3>
        <div className="card" style={{ padding: "var(--space-4)" }}>
          <div className="row" style={{ alignItems: "flex-end", height: 100, gap: 4 }}>
            {data.concurrency.map((c) => (
              <div
                key={c.week_start}
                title={`${dateFmt(c.week_start)}: ${c.count}`}
                style={{
                  flex: 1,
                  height: `${(c.count / maxConcurrency) * 100}%`,
                  minHeight: 2,
                  background: peakSet.has(c.week_start) ? "var(--color-accent-700)" : "var(--color-accent-400)",
                }}
              />
            ))}
          </div>
          {peakSet.size > 0 && <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>Peak week{peakSet.size > 1 ? "s" : ""}: {[...peakSet].map(dateFmt).join(", ")}</div>}
        </div>
      </div>

      <div className="section">
        <h3>Revenue Projection</h3>
        <div className="card" style={{ padding: "var(--space-4)" }}>
          <div className="row" style={{ alignItems: "flex-end", height: 160, gap: 6 }}>
            {data.revenue_projection.map((r) => {
              const total = r.collected + r.scheduled;
              return (
                <div
                  key={r.month}
                  title={`${r.month}: ${money(total)} (${money(r.collected)} collected, ${money(r.scheduled)} scheduled)`}
                  style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", height: "100%" }}
                >
                  <div
                    className="muted"
                    style={{ fontSize: 10, marginBottom: 2, writingMode: total > 0 ? "vertical-rl" : undefined, whiteSpace: "nowrap" }}
                  >
                    {total > 0 ? money(total) : ""}
                  </div>
                  <div style={{ flex: 1, display: "flex", flexDirection: "column-reverse", width: "100%" }}>
                    <div style={{ height: `${(r.collected / maxRevenueMonth) * 100}%`, background: "var(--color-accent-700)" }} />
                    <div style={{ height: `${(r.scheduled / maxRevenueMonth) * 100}%`, background: "var(--color-accent-300)" }} />
                  </div>
                  <div className="muted" style={{ fontSize: 10, marginTop: 4, whiteSpace: "nowrap" }}>
                    {r.month}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="row" style={{ fontSize: 11, marginTop: "var(--space-2)" }}>
            <span className="icon-text">
              <span style={{ width: 10, height: 10, background: "var(--color-accent-700)", display: "inline-block" }} /> Collected
            </span>
            <span className="icon-text">
              <span style={{ width: 10, height: 10, background: "var(--color-accent-300)", display: "inline-block" }} /> Scheduled
            </span>
          </div>
        </div>

        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Total</th>
                <th>Collected</th>
              </tr>
            </thead>
            <tbody>
              {data.revenue_by_project.map((row) => (
                <tr key={row.project_id}>
                  <td>{row.project_name}</td>
                  <td>{money(row.total)}</td>
                  <td>{money(row.collected)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
