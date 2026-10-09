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
  icon: LucideIcon;
  description: string;
}

export const APP_NAV: ReadonlyArray<NavItem> = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, description: "Overview of your business" },
  { href: "/documents", label: "Documents", icon: FileUp, description: "Upload sales sheets, invoices and statements" },
  { href: "/records", label: "Invoices & payments", icon: ReceiptIndianRupee, description: "Your business records" },
  { href: "/copilot", label: "AI Copilot", icon: MessageSquareText, description: "Ask questions about your business" },
  { href: "/settings", label: "Settings", icon: Settings, description: "Language and business preferences" },
];
