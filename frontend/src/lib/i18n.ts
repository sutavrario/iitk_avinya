import { useWorkspace } from "@/components/providers/workspace-provider";
import type { LanguageCode } from "@/lib/types";

export const DICTIONARY: Record<LanguageCode, Record<string, string>> = {
  en: {
    "nav.dashboard": "Dashboard",
    "nav.documents": "Documents",
    "nav.records": "Invoices & payments",
    "nav.copilot": "AI Copilot",
    "nav.settings": "Settings",
    "common.loading": "Loading...",
    "common.error": "An error occurred",
    "common.save": "Save",
    "common.cancel": "Cancel",
    "dashboard.upload_records": "Upload records",
    "dashboard.total_sales": "Total sales",
    "dashboard.this_financial_year": "This financial year",
    "dashboard.cash_collected": "Cash collected",
    "dashboard.payments_received": "Payments received",
    "dashboard.customers_owe_you": "Customers owe you",
    "dashboard.unpaid_invoices": "Unpaid invoices",
    "dashboard.overdue": "Overdue",
    "dashboard.past_due_date": "Past due date",
    "dashboard.sales_vs_expenses": "Sales vs expenses",
    "dashboard.monthly_this_financial_year": "Monthly, this financial year",
    "dashboard.money_owed_to_you": "Money owed to you",
    "dashboard.unpaid_invoices_by_late": "Unpaid invoices by how late they are",
    "dashboard.who_to_follow_up_with": "Who to follow up with",
    "dashboard.customers_largest_unpaid": "Customers with the largest unpaid balance",
    "dashboard.no_unpaid_invoices": "No unpaid invoices. Nice work!",
    "dashboard.your_business_glance": "Your business at a glance",
  },
  bn: {
    "nav.dashboard": "ড্যাশবোর্ড",
    "nav.documents": "ডকুমেন্ট",
    "nav.records": "ইনভয়েস এবং পেমেন্ট",
    "nav.copilot": "এআই কোপাইলট",
    "nav.settings": "সেটিংস",
    "common.loading": "লোড হচ্ছে...",
    "common.error": "একটি ত্রুটি ঘটেছে",
    "common.save": "সংরক্ষণ করুন",
    "common.cancel": "বাতিল করুন",
    "dashboard.upload_records": "রেকর্ড আপলোড করুন",
    "dashboard.total_sales": "মোট বিক্রয়",
    "dashboard.this_financial_year": "এই আর্থিক বছরে",
    "dashboard.cash_collected": "সংগৃহীত নগদ",
    "dashboard.payments_received": "পেমেন্ট প্রাপ্ত",
    "dashboard.customers_owe_you": "গ্রাহকদের কাছে পাওনা",
    "dashboard.unpaid_invoices": "অপরিশোধিত ইনভয়েস",
    "dashboard.overdue": "মেয়াদোত্তীর্ণ",
    "dashboard.past_due_date": "অতিক্রান্ত শেষ তারিখ",
    "dashboard.sales_vs_expenses": "বিক্রয় বনাম ব্যয়",
    "dashboard.monthly_this_financial_year": "মাসিক, এই আর্থিক বছরে",
    "dashboard.money_owed_to_you": "আপনার পাওনা অর্থ",
    "dashboard.unpaid_invoices_by_late": "কতদিন ধরে বকেয়া অনুযায়ী অপরিশোধিত ইনভয়েস",
    "dashboard.who_to_follow_up_with": "কাকে ফলো-আপ করতে হবে",
    "dashboard.customers_largest_unpaid": "সর্বোচ্চ বকেয়া থাকা গ্রাহক",
    "dashboard.no_unpaid_invoices": "কোনো বকেয়া ইনভয়েস নেই। দারুণ কাজ!",
    "dashboard.your_business_glance": "এক নজরে আপনার ব্যবসা",
  },
  hi: {
    "nav.dashboard": "डैशबोर्ड",
    "nav.documents": "दस्तावेज़",
    "nav.records": "चालान और भुगतान",
    "nav.copilot": "एआई कोपायलट",
    "nav.settings": "सेटिंग्स",
    "common.loading": "लोड हो रहा है...",
    "common.error": "एक त्रुटि हुई",
    "common.save": "सहेजें",
    "common.cancel": "रद्द करें",
    "dashboard.upload_records": "रिकॉर्ड अपलोड करें",
    "dashboard.total_sales": "कुल बिक्री",
    "dashboard.this_financial_year": "इस वित्तीय वर्ष में",
    "dashboard.cash_collected": "नकद प्राप्त",
    "dashboard.payments_received": "भुगतान प्राप्त",
    "dashboard.customers_owe_you": "ग्राहकों पर बकाया",
    "dashboard.unpaid_invoices": "अवैतनिक चालान",
    "dashboard.overdue": "अतिदेय",
    "dashboard.past_due_date": "नियत तारीख बीत चुकी",
    "dashboard.sales_vs_expenses": "बिक्री बनाम खर्च",
    "dashboard.monthly_this_financial_year": "मासिक, इस वित्तीय वर्ष में",
    "dashboard.money_owed_to_you": "आपका बकाया पैसा",
    "dashboard.unpaid_invoices_by_late": "कितने समय से बकाया है, उसके अनुसार अवैतनिक चालान",
    "dashboard.who_to_follow_up_with": "किसे फॉलो-अप करना है",
    "dashboard.customers_largest_unpaid": "सबसे बड़े बकाये वाले ग्राहक",
    "dashboard.no_unpaid_invoices": "कोई बकाया चालान नहीं। बहुत बढ़िया!",
    "dashboard.your_business_glance": "एक नज़र में आपका व्यवसाय",
  },
  ta: {}, te: {}, mr: {}, gu: {}, kn: {}, ml: {}, pa: {},
};

/**
 * A lightweight translation hook.
 * Returns a `t(key, fallback)` function.
 */
export function useTranslation() {
  const { state } = useWorkspace();
  
  // Default to English if not ready
  const lang = state.status === "ready" 
    ? state.me.user.preferences.interfaceLanguage || "en"
    : "en";

  const dict = DICTIONARY[lang] || DICTIONARY.en;

  const t = (key: string, fallback?: string): string => {
    return dict[key] || DICTIONARY.en[key] || fallback || key;
  };

  return { t, lang };
}
