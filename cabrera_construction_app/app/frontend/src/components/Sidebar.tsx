import { useLocation, useNavigate } from "react-router-dom";
import { useProjectContext } from "../context/ProjectContext";
import { COMPANY_NAV, WORKFLOW_STEPS } from "../nav";

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { selectedProjectId } = useProjectContext();

  return (
    <aside className="sidebar desktop-only">
      <div className="sidebar-logo">
        <img src="/cabrera-logo.png" alt="Cabrera Construction" />
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
              {step.label}
            </a>
          );
        })}

        <div className="sidebar-group-label">Company</div>
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
              {item.label}
            </a>
          );
        })}
      </nav>

      <div className="sidebar-user">
        <div>Samuel Cabrera</div>
        <div className="sidebar-user-role">Owner / Admin</div>
      </div>
    </aside>
  );
}
