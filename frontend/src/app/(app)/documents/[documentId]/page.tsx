import type { Metadata } from "next";
import { DocumentReviewView } from "@/components/ingestion/document-review-view";

export const metadata: Metadata = { title: "Review document" };

export default function DocumentReviewPage() {
  return <DocumentReviewView />;
}
