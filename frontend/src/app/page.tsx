import {
  ArrowRight,
  BarChart3,
  Bell,
  FileSpreadsheet,
  Languages,
  MessageSquareText,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { SiteHeader } from "@/components/marketing/site-header";
import { Logo } from "@/components/shared/logo";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { LANGUAGES } from "@/lib/constants";
import { cn } from "@/lib/utils";

const FEATURES = [
  {
    icon: FileSpreadsheet,
    title: "Works with what you already have",
    body: "Upload Excel sheets, Tally exports, PDF invoices or even photos of your bahi-khata. No new software to learn.",
  },
  {
    icon: BarChart3,
    title: "See your business at a glance",
    body: "Sales, expenses, money owed to you and cash collected — on one clear dashboard, in ₹ lakh and crore.",
  },
  {
    icon: Bell,
    title: "Collect payments on time",
    body: "Spot overdue invoices early and know which customers to follow up with this week.",
  },
  {
    icon: MessageSquareText,
    title: "Ask in plain words",
    body: "“Which customers owe me the most?” “How did September compare to August?” Get answers from your own records.",
  },
];

const STEPS = [
  { title: "Tell us about your business", body: "Two minutes. Only your business name, industry and city are required." },
  { title: "Upload your records", body: "Add sales registers, invoices and bank statements whenever you're ready." },
  { title: "Get insights and answers", body: "Track cash flow and ask the copilot questions in your language." },
];

export default function LandingPage() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <section className="relative overflow-hidden">
          <div
            aria-hidden
            className="absolute inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_0%,color-mix(in_oklch,var(--primary)_14%,transparent),transparent)]"
          />
          <div className="mx-auto max-w-6xl px-4 pt-16 pb-20 text-center sm:px-6 sm:pt-24">
            <p className="mx-auto mb-5 inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground">
              <span className="size-1.5 rounded-full bg-brand-accent" aria-hidden />
              Built for Indian small businesses
            </p>
            <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
              Your business numbers, explained — <span className="text-primary">in your language</span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg text-pretty text-muted-foreground">
              VyaparAI reads your sales sheets, invoices and payments, then shows you where your money is
              and what to do next. Like a smart munim, available 24×7.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link href="/sign-up" className={cn(buttonVariants({ size: "lg" }), "h-11 px-5 text-base")}>
                Get started free <ArrowRight data-icon="inline-end" />
              </Link>
              <Link
                href="/sign-in"
                className={cn(buttonVariants({ size: "lg", variant: "outline" }), "h-11 px-5 text-base")}
              >
                I already have an account
              </Link>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              No credit card. No Excel file needed to start.
            </p>
          </div>
        </section>

        <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 sm:px-6">
          <h2 className="text-center text-2xl font-semibold tracking-tight sm:text-3xl">
            Everything a busy owner needs, nothing extra
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <Card key={title}>
                <CardContent className="flex gap-4">
                  <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="size-5" aria-hidden />
                  </div>
                  <div>
                    <h3 className="font-medium">{title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{body}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section id="how-it-works" className="scroll-mt-20 border-y bg-muted/40">
          <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
            <h2 className="text-center text-2xl font-semibold tracking-tight sm:text-3xl">How it works</h2>
            <ol className="mt-10 grid gap-6 md:grid-cols-3">
              {STEPS.map((s, i) => (
                <li key={s.title} className="rounded-xl border bg-card p-6">
                  <span className="grid size-8 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                    {i + 1}
                  </span>
                  <h3 className="mt-4 font-medium">{s.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="languages" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-16 sm:px-6">
          <div className="grid items-center gap-10 md:grid-cols-2">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-primary">
                <Languages className="size-4" aria-hidden /> Multilingual
              </div>
              <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                Ask questions in Hindi, Bengali, Tamil and more
              </h2>
              <p className="mt-3 text-muted-foreground">
                Choose the language you&apos;re most comfortable with. You can change it anytime in settings.
              </p>
              <p className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
                <ShieldCheck className="size-4 text-success" aria-hidden />
                Your records stay private to your business account.
              </p>
            </div>
            <ul className="flex flex-wrap gap-2" aria-label="Supported languages">
              {LANGUAGES.map((l) => (
                <li key={l.value} className="rounded-full border bg-card px-4 py-2 text-sm">
                  <span lang={l.value}>{l.nativeLabel}</span>
                  {l.value !== "en" && <span className="ml-1.5 text-muted-foreground">· {l.label}</span>}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
          <div className="rounded-2xl bg-primary px-6 py-12 text-center text-primary-foreground sm:px-12">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Set up your business in 2 minutes</h2>
            <p className="mx-auto mt-3 max-w-xl text-primary-foreground/80">
              Start with the basics. Add your records later, whenever you&apos;re ready.
            </p>
            <Link
              href="/sign-up"
              className={cn(buttonVariants({ variant: "secondary", size: "lg" }), "mt-6 h-11 px-5 text-base")}
            >
              Get started <ArrowRight data-icon="inline-end" />
            </Link>
          </div>
        </section>
      </main>
      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-6 text-sm text-muted-foreground sm:flex-row sm:px-6">
          <Logo />
          <p>© {new Date().getFullYear()} VyaparAI · Hackathon prototype</p>
        </div>
      </footer>
    </>
  );
}
