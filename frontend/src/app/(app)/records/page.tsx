import type { Metadata } from "next";
import { RecordsView } from "@/components/records/records-view";

export const metadata: Metadata = { title: "Invoices & payments" };

export default function RecordsPage() {
  return <RecordsView />;
}
