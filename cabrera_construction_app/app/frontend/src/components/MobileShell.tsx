import { Menu, X } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
// See Sidebar.tsx for why this is a module import, not a public/ path string.
import cabreraLogo from "../assets/cabrera-logo.png";
import { useProjectContext } from "../context/ProjectContext";
import { COMPANY_NAV, WORKFLOW_STEPS } from "../nav";

export function MobileHeader({ title }: { title: string }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <>
      <header className="mobile-header mobile-only">
        <div className="mobile-header-logo">
          <img src={cabreraLogo} alt="Cabrera Construction" style={{ height: 20 }} />
          <span style={{ fontSize: 15 }}>{title}</span>
        </div>
        <button className="btn btn-icon" aria-label="Menu" onClick={() => setMenuOpen(true)}>
          <Menu size={18} strokeWidth={1.5} />
        </button>
      </header>

      {menuOpen && (
        <div className="dialog-backdrop" onClick={() => setMenuOpen(false)}>
          <div className="dialog" style={{ alignSelf: "flex-start", marginTop: 56 }} onClick={(e) => e.stopPropagation()}>
            <div className="row-between">
              <div className="dialog-title">Company</div>
              <button className="btn btn-icon" onClick={() => setMenuOpen(false)}>
                <X size={16} strokeWidth={1.5} />
              </button>
            </div>
            <div className="stack">
              {COMPANY_NAV.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.path}
                    className="btn btn-secondary btn-block"
                    style={{ justifyContent: "flex-start" }}
                    onClick={() => {
                      setMenuOpen(false);
                      navigate(item.path);
                    }}
                  >
                    <Icon size={16} strokeWidth={1.5} />
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function MobileTabBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectContext();

  return (
    <nav className="mobile-tabbar mobile-only">
      {WORKFLOW_STEPS.map((step) => {
        const path = step.path(selectedProjectId);
        const active = location.pathname === path;
        const Icon = step.icon;
        return (
          <a
            key={step.number}
            className={`mobile-tab${active ? " active" : ""}`}
            href={path}
            onClick={(e) => {
              e.preventDefault();
              navigate(path);
            }}
          >
            <Icon size={16} strokeWidth={1.5} />
            {step.mobileLabel}
          </a>
        );
      })}
    </nav>
  );
}
