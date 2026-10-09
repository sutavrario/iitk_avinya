import {
  FileUp,
  LayoutDashboard,
  MessageSquareText,
  ReceiptIndianRupee,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  i18nKey?: string;
  icon: LucideIcon;
  description: string;
}

export const APP_NAV: ReadonlyArray<NavItem> = [
  { href: "/dashboard", label: "Dashboard", i18nKey: "nav.dashboard", icon: LayoutDashboard, description: "Overview of your business" },
  { href: "/documents", label: "Documents", i18nKey: "nav.documents", icon: FileUp, description: "Upload sales sheets, invoices and statements" },
  { href: "/records", label: "Invoices & payments", i18nKey: "nav.records", icon: ReceiptIndianRupee, description: "Your business records" },
  { href: "/copilot", label: "AI Copilot", i18nKey: "nav.copilot", icon: MessageSquareText, description: "Ask questions about your business" },
  { href: "/settings", label: "Settings", i18nKey: "nav.settings", icon: Settings, description: "Language and business preferences" },
];
