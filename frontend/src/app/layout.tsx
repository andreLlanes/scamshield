import type { Metadata } from "next";

import { Header } from "@/components/layout/Header";
import { SystemStatus } from "@/components/layout/SystemStatus";

import "./globals.css";

export const metadata: Metadata = {
  title: "ScamShield — Audio Scam Detection & Explainability",
  description:
    "Upload a recording of a suspicious phone call and get an explainable scam assessment: risk score, verified claims, manipulation tactics, and what to do next.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <Header />
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>
        <footer className="mt-16 border-t border-[var(--color-hairline)]">
          <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-6 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <SystemStatus />
            <p className="text-xs text-slate-500">
              ScamShield is a decision aid, not a verdict. Always verify with the
              organisation directly.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
