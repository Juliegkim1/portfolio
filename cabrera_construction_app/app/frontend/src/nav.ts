import {
  BarChart3,
  Building2,
  FileSignature,
  FileSpreadsheet,
  GitPullRequest,
  Landmark,
  Receipt,
  Scale,
  ScrollText,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavStep {
  number: number;
  label: string;
  mobileLabel: string;
  icon: LucideIcon;
  path: (projectId: number | null) => string;
}

export const WORKFLOW_STEPS: NavStep[] = [
  { number: 1, label: "Customers & Projects", mobileLabel: "Projects", icon: Building2, path: () => "/projects" },
  { number: 2, label: "Estimate Upload", mobileLabel: "Estimate", icon: FileSpreadsheet, path: () => "/estimate-upload" },
  { number: 3, label: "Project Scope & Payment Schedule", mobileLabel: "Scope", icon: ScrollText, path: (id) => (id ? `/projects/${id}/scope` : "/projects") },
  { number: 4, label: "Contract Package", mobileLabel: "Contract", icon: FileSignature, path: (id) => (id ? `/projects/${id}/contract` : "/projects") },
  { number: 5, label: "Change Orders", mobileLabel: "Changes", icon: GitPullRequest, path: (id) => (id ? `/projects/${id}/change-orders` : "/projects") },
  { number: 6, label: "Invoices", mobileLabel: "Invoices", icon: Receipt, path: (id) => (id ? `/projects/${id}/invoices` : "/projects") },
  { number: 7, label: "Reconciliation & Closing", mobileLabel: "Recon.", icon: Scale, path: (id) => (id ? `/projects/${id}/reconciliation` : "/projects") },
];

export interface CompanyNavItem {
  label: string;
  icon: LucideIcon;
  path: string;
}

export const COMPANY_NAV: CompanyNavItem[] = [
  { label: "Analytics", icon: BarChart3, path: "/analytics" },
  { label: "Operational Reconciliation", icon: Landmark, path: "/operational-reconciliation" },
  { label: "Team & Users", icon: Users, path: "/team" },
  { label: "Business Expenses", icon: Wallet, path: "/business-expenses" },
];
