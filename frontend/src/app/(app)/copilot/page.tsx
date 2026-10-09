import type { Metadata } from "next";
import { CopilotView } from "@/components/copilot/copilot-view";

export const metadata: Metadata = { title: "AI Copilot" };

export default function CopilotPage() {
  return <CopilotView />;
}
