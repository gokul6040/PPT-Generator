import Link from "next/link";
import type { ReactNode } from "react";

type LegalSection = {
  heading: string;
  content: ReactNode;
};

type LegalPageProps = {
  title: string;
  summary: string;
  sections: LegalSection[];
};

export function LegalPage({ title, summary, sections }: LegalPageProps) {
  return (
    <main className="h-dvh overflow-y-auto bg-[#0c0e12] px-6 py-10 text-slate-200 md:px-10 lg:px-16">
      <article className="mx-auto max-w-3xl">
        <Link
          href="/"
          className="text-sm font-medium text-sky-300 transition-colors hover:text-sky-200"
        >
          &larr; Back to TurnB PPT Agent
        </Link>

        <header className="mt-8 border-b border-[#2a3140] pb-8">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-sky-300">
            TurnB PPT Agent
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-100 md:text-4xl">
            {title}
          </h1>
          <p className="mt-4 text-base leading-7 text-slate-400">{summary}</p>
          <p className="mt-3 text-sm text-slate-500">Effective: August 13, 2026</p>
        </header>

        <div className="space-y-8 py-8">
          {sections.map((section) => (
            <section key={section.heading}>
              <h2 className="text-xl font-semibold text-slate-100">
                {section.heading}
              </h2>
              <div className="mt-3 space-y-3 text-sm leading-7 text-slate-300 md:text-base">
                {section.content}
              </div>
            </section>
          ))}
        </div>

        <footer className="border-t border-[#2a3140] py-6 text-sm text-slate-500">
          This pilot notice should be reviewed by TurnB legal and security owners
          before organization-wide or external distribution.
        </footer>
      </article>
    </main>
  );
}
