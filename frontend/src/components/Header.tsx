import { HelpCircle } from "lucide-react";

export function Header() {
  return (
    <header className="flex shrink-0 items-start justify-between gap-4 border-b border-[#2a3140] bg-[#12151c] px-6 py-5 md:px-10 lg:px-16">
      <div className="flex items-center gap-3.5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#3d4f6f] bg-[#1a2030] text-sm font-semibold tracking-tight text-slate-100">
          TB
        </div>
        <div>
          <h1 className="text-[1.05rem] font-semibold tracking-tight text-slate-100">
            TurnB Case Study PPT Agent
          </h1>
          <p className="mt-0.5 text-sm text-slate-400">
            Build case study presentations from rough project content
          </p>
        </div>
      </div>
      <button
        type="button"
        aria-label="Help"
        className="rounded-full p-2 text-slate-400 transition-colors hover:bg-[#222833] hover:text-slate-200"
      >
        <HelpCircle className="h-5 w-5" strokeWidth={1.75} />
      </button>
    </header>
  );
}
