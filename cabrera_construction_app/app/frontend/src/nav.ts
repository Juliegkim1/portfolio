import {
  BarChart3,
  Building2,
  FileSignature,
  FileSpreadsheet,
  FolderInput,
  GitPullRequest,
  Landmark,
  Receipt,
  Scale,
  ScrollText,
  Settings,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavStep {
  number: number;
  labelKey: string;
  mobileLabelKey: string;
  icon: LucideIcon;
  path: (projectId: number | null) => string;
}

// label/mobileLabel are i18next keys (see src/i18n), resolved at render time
// with useTranslation() in Sidebar/MobileShell — not literal text, so the
// nav relabels itself immediately when the language setting changes.
export const WORKFLOW_STEPS: NavStep[] = [
  { number: 1, labelKey: "nav.step1", mobileLabelKey: "nav.step1Mobile", icon: Building2, path: () => "/projects" },
  { number: 2, labelKey: "nav.step2", mobileLabelKey: "nav.step2Mobile", icon: FileSpreadsheet, path: () => "/estimate-upload" },
  { number: 3, labelKey: "nav.step3", mobileLabelKey: "nav.step3Mobile", icon: ScrollText, path: (id) => (id ? `/projects/${id}/scope` : "/projects") },
  { number: 4, labelKey: "nav.step4", mobileLabelKey: "nav.step4Mobile", icon: FileSignature, path: (id) => (id ? `/projects/${id}/contract` : "/projects") },
  { number: 5, labelKey: "nav.step5", mobileLabelKey: "nav.step5Mobile", icon: GitPullRequest, path: (id) => (id ? `/projects/${id}/change-orders` : "/projects") },
  { number: 6, labelKey: "nav.step6", mobileLabelKey: "nav.step6Mobile", icon: Receipt, path: (id) => (id ? `/projects/${id}/invoices` : "/projects") },
  { number: 7, labelKey: "nav.step7", mobileLabelKey: "nav.step7Mobile", icon: Scale, path: (id) => (id ? `/projects/${id}/reconciliation` : "/projects") },
];

export interface CompanyNavItem {
  labelKey: string;
  icon: LucideIcon;
  path: string;
}

export const COMPANY_NAV: CompanyNavItem[] = [
  { labelKey: "nav.analytics", icon: BarChart3, path: "/analytics" },
  { labelKey: "nav.operationalReconciliation", icon: Landmark, path: "/operational-reconciliation" },
  { labelKey: "nav.importFromDrive", icon: FolderInput, path: "/import-from-drive" },
  { labelKey: "nav.settings", icon: Settings, path: "/settings" },
  { labelKey: "nav.businessExpenses", icon: Wallet, path: "/business-expenses" },
];
