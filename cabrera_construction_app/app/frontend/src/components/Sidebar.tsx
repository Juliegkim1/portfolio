import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
// Imported (not referenced via a public/ path string) so Vite bundles it
// through its asset pipeline into dist/assets/ — the only path the backend
// actually serves statically in production (see main.py's StaticFiles
// mount, which only covers /assets/*). A string path like "/cabrera-
// logo.png" silently 404s there (falls through to the SPA catch-all,
// which returns index.html instead of the image) even though it works
// fine in local dev, where Vite's dev server serves public/ at the root.
import cabreraLogo from "../assets/cabrera-logo.png";
import { useProjectContext } from "../context/ProjectContext";
import { COMPANY_NAV, WORKFLOW_STEPS } from "../nav";

export function Sidebar() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectContext();

  return (
    <aside className="sidebar desktop-only">
      <div className="sidebar-logo">
        <img src={cabreraLogo} alt="Cabrera Construction" />
      </div>

      <nav className="sidebar-nav">
        {WORKFLOW_STEPS.map((step) => {
          const path = step.path(selectedProjectId);
          const active = location.pathname === path || (step.number === 1 && location.pathname === "/");
          const Icon = step.icon;
          return (
            <a
              key={step.number}
              className={`sidebar-step${active ? " active" : ""}`}
              href={path}
              onClick={(e) => {
                e.preventDefault();
                navigate(path);
              }}
            >
              <span className="sidebar-step-num">{step.number}</span>
              <Icon size={15} strokeWidth={1.5} />
              {t(step.labelKey)}
            </a>
          );
        })}

        <div className="sidebar-group-label">{t("nav.company")}</div>
        {COMPANY_NAV.map((item) => {
          const active = location.pathname === item.path;
          const Icon = item.icon;
          return (
            <a
              key={item.path}
              className={`sidebar-step${active ? " active" : ""}`}
              href={item.path}
              onClick={(e) => {
                e.preventDefault();
                navigate(item.path);
              }}
            >
              <Icon size={15} strokeWidth={1.5} />
              {t(item.labelKey)}
            </a>
          );
        })}
      </nav>

      <div className="sidebar-user">
        <div>Samuel Cabrera</div>
        <div className="sidebar-user-role">{t("nav.ownerRole")}</div>
      </div>
    </aside>
  );
}
