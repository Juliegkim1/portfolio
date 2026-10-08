import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState } from "../components/StateViews";
import { dateFmt, money, moneyWhole } from "../format";

const PX_PER_DAY = 5;
const DAY_MS = 86_400_000;

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}
function monthKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function monthKeyFromDateStr(value: string): string {
  return monthKey(new Date(`${value}T00:00:00`));
}
function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}
function shiftMonthKey(key: string, delta: number): string {
  const [y, m] = key.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return monthKey(d);
}
function weekLabel(value: string): string {
  const d = new Date(`${value}T00:00:00`);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
function weekRangeLabel(weekStart: string): string {
  const start = new Date(`${weekStart}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  return `${weekLabel(weekStart)} – ${end.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
}

export function AnalyticsPage() {
  const { t } = useTranslation();
  const [includePending, setIncludePending] = useState(false);
  const query = useQuery({ queryKey: ["analytics", includePending], queryFn: () => api.analytics.get(includePending) });

  const todayKey = monthKey(new Date());
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  // Hooks must run unconditionally on every render — this has to sit above
  // the loading/error early returns below, not after them, or the hook
  // count differs between the loading render and the loaded render ("more
  // hooks than during the previous render").
  const availableMonths = useMemo(() => {
    const keys = new Set((query.data?.concurrency ?? []).map((c) => monthKeyFromDateStr(c.week_start)));
    return [...keys].sort();
  }, [query.data]);

  if (query.isLoading) {
    return (
      <AppShell title={t("nav.analytics")}>
        <LoadingState />
      </AppShell>
    );
  }
  if (query.isError) {
    return (
      <AppShell title={t("nav.analytics")}>
        <ErrorState error={query.error} />
      </AppShell>
    );
  }

  const data = query.data!;
  const today = new Date();

  // --- Project Timeline: real pixel-per-day scale (not a percentage of a
  // fixed-width container) so the chart can actually scroll horizontally
  // to older work instead of squeezing every project's history into one
  // narrow strip — a year of projects needs real width, not a smaller bar.
  const allDates = data.timeline.flatMap((p) => [new Date(p.start_date), new Date(p.end_date)]);
  const minDate = allDates.length ? startOfMonth(new Date(Math.min(...allDates.map((d) => d.getTime())))) : startOfMonth(today);
  const maxDateRaw = allDates.length ? new Date(Math.max(...allDates.map((d) => d.getTime()))) : today;
  const totalDays = Math.max(30, Math.round((maxDateRaw.getTime() - minDate.getTime()) / DAY_MS) + 14);
  const trackWidth = totalDays * PX_PER_DAY;
  const dayOffset = (d: Date) => Math.round((d.getTime() - minDate.getTime()) / DAY_MS);
  const leftPx = (d: Date) => dayOffset(d) * PX_PER_DAY;

  const monthTicks: { key: string; left: number }[] = [];
  for (let m = new Date(minDate); m.getTime() <= maxDateRaw.getTime(); m = new Date(m.getFullYear(), m.getMonth() + 1, 1)) {
    monthTicks.push({ key: monthKey(m), left: leftPx(m) });
  }

  // --- Projects at the Same Time: filtered to one month at a time (a full
  // history of weekly bars in one view stops being readable past a few
  // months) — defaults to the current month when there's data for it,
  // otherwise the most recent month that has any. (availableMonths itself
  // is computed above, before the loading/error early returns — see why.)
  const effectiveMonth = selectedMonth ?? (availableMonths.includes(todayKey) ? todayKey : availableMonths[availableMonths.length - 1] ?? todayKey);
  // Only weeks with at least one overlapping project are worth a row — an
  // empty week added nothing to the old bar chart either (a bar of height
  // 0), it's just more obviously dead space as a table row.
  const monthWeeks = data.concurrency.filter((c) => monthKeyFromDateStr(c.week_start) === effectiveMonth && c.count > 0);
  const monthIndex = availableMonths.indexOf(effectiveMonth);

  const maxRevenueMonth = Math.max(1, ...data.revenue_projection.map((r) => r.collected + r.scheduled));

  return (
    <AppShell title={t("nav.analytics")} context={t("analytics.context")}>
      <div className="kpi-grid section">
        <div className="card">
          <div className="card-kicker">{t("analytics.inProgressToday")}</div>
          <div className="kpi-value">{data.kpis.in_progress_today}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("analytics.signedContractValue")}</div>
          <div className="kpi-value">{money(data.kpis.signed_contract_value)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("analytics.projectedRemaining")}</div>
          <div className="kpi-value">{money(data.kpis.projected_remaining)}</div>
          <div className="kpi-sub">{t("analytics.dueNext90Days", { amount: money(data.kpis.due_next_90_days) })}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("analytics.collectedToDate")}</div>
          <div className="kpi-value">{money(data.kpis.collected_to_date)}</div>
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>{t("analytics.projectTimeline")}</h3>
          <label className="radio">
            <input type="checkbox" checked={includePending} onChange={(e) => setIncludePending(e.target.checked)} style={{ position: "static", opacity: 1, width: "auto", height: "auto" }} />
            {t("analytics.includePending")}
          </label>
        </div>
        {data.timeline.length === 0 ? (
          <div className="empty-state">{t("analytics.noTimelineData")}</div>
        ) : (
          <div className="card" style={{ padding: "var(--space-4)" }}>
            {/* One shared horizontal-scroll container for the month-tick
                header AND every project's bar row, stacked together inside
                the same scrolling width — so scrolling stays in sync across
                rows instead of each row (and the header) scrolling
                independently. Only the name-label column sits outside it,
                staying fixed while the chart itself scrolls. */}
            <div style={{ display: "flex" }}>
              <div style={{ width: 160, flex: "none" }}>
                <div style={{ height: 24 }} />
                {data.timeline.map((p) => (
                  <div key={p.id} className="muted" style={{ height: 16, marginBottom: 10, fontSize: 12, paddingRight: 8, display: "flex", alignItems: "center" }}>
                    {p.name}
                  </div>
                ))}
              </div>
              <div style={{ overflowX: "auto", flex: 1 }}>
                <div style={{ position: "relative", width: trackWidth }}>
                  <div style={{ position: "relative", height: 24 }}>
                    {monthTicks.map((tick) => (
                      <div key={tick.key} className="muted" style={{ position: "absolute", left: tick.left, top: 0, fontSize: 11, borderLeft: "1px solid var(--color-divider)", paddingLeft: 4, height: "100%" }}>
                        {monthLabel(tick.key).split(" ")[0]}
                      </div>
                    ))}
                  </div>
                  {data.timeline.map((p) => (
                    <div key={p.id} style={{ position: "relative", height: 16, marginBottom: 10, background: "var(--color-surface)" }}>
                      <div
                        title={`${p.name}: ${dateFmt(p.start_date)} – ${dateFmt(p.end_date)}`}
                        style={{
                          position: "absolute",
                          left: leftPx(new Date(p.start_date)),
                          width: Math.max(PX_PER_DAY, leftPx(new Date(p.end_date)) - leftPx(new Date(p.start_date))),
                          height: "100%",
                          background: p.signed ? "var(--color-accent-200)" : "transparent",
                          border: `1.5px ${p.signed ? "solid" : "dashed"} var(--color-accent-700)`,
                        }}
                      />
                    </div>
                  ))}
                  {today >= minDate && today <= maxDateRaw && (
                    <div
                      style={{ position: "absolute", left: leftPx(today), top: 24, bottom: 0, width: 1, background: "var(--color-accent-700)" }}
                      title={t("analytics.today")}
                    />
                  )}
                </div>
              </div>
            </div>
            <div className="muted" style={{ fontSize: 11, marginTop: "var(--space-2)" }}>
              {t("analytics.scrollHint")}
            </div>
          </div>
        )}
      </div>

      <div className="section">
        <div className="row-between" style={{ flexWrap: "wrap", gap: "var(--space-2)" }}>
          <h3>{t("analytics.projectsAtSameTime")}</h3>
          <div className="row" style={{ gap: "var(--space-1)" }}>
            <button className="btn btn-icon" disabled={monthIndex <= 0} onClick={() => setSelectedMonth(availableMonths[monthIndex - 1])}>
              <ChevronLeft size={14} strokeWidth={1.5} />
            </button>
            <select className="input" style={{ minWidth: 160 }} value={effectiveMonth} onChange={(e) => setSelectedMonth(e.target.value)}>
              {availableMonths.length === 0 && <option value={effectiveMonth}>{monthLabel(effectiveMonth)}</option>}
              {availableMonths.map((key) => (
                <option key={key} value={key}>
                  {monthLabel(key)}
                  {key === todayKey ? ` (${t("analytics.currentMonth")})` : ""}
                </option>
              ))}
            </select>
            <button className="btn btn-icon" disabled={monthIndex === -1 || monthIndex >= availableMonths.length - 1} onClick={() => setSelectedMonth(availableMonths[monthIndex + 1])}>
              <ChevronRight size={14} strokeWidth={1.5} />
            </button>
          </div>
        </div>
        {monthWeeks.length === 0 ? (
          <div className="card" style={{ padding: "var(--space-4)" }}>
            <div className="empty-state">{t("analytics.noConcurrencyData")}</div>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("analytics.week")}</th>
                  <th>{t("common.customer")}</th>
                  <th>{t("common.address")}</th>
                </tr>
              </thead>
              <tbody>
                {monthWeeks.flatMap((c) =>
                  c.projects.map((p, i) => (
                    <tr key={`${c.week_start}-${p.id}`}>
                      {i === 0 ? (
                        <td rowSpan={c.projects.length} className="muted" style={{ verticalAlign: "top", whiteSpace: "nowrap" }}>
                          {weekRangeLabel(c.week_start)}
                        </td>
                      ) : null}
                      <td>{p.customer_name}</td>
                      <td>{p.property_address}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="section">
        <h3>{t("analytics.revenueProjection")}</h3>
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
                  <div className="muted" style={{ fontSize: 10, marginBottom: 2, whiteSpace: "nowrap" }}>
                    {total > 0 ? moneyWhole(total) : ""}
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
              <span style={{ width: 10, height: 10, background: "var(--color-accent-700)", display: "inline-block" }} /> {t("analytics.collected")}
            </span>
            <span className="icon-text">
              <span style={{ width: 10, height: 10, background: "var(--color-accent-300)", display: "inline-block" }} /> {t("analytics.scheduled")}
            </span>
          </div>
        </div>

        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>{t("common.project")}</th>
                <th>{t("common.total")}</th>
                <th>{t("analytics.collected")}</th>
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
