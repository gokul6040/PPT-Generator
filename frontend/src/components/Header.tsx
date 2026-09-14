"use client";

import { HelpCircle, X } from "lucide-react";
import { useState } from "react";

export function Header() {
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  return (
    <>
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-[#302e3a] bg-[#141319] px-6 py-5 md:px-10 lg:px-16">
        <div className="flex items-center gap-3.5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#7656f5] bg-[#6042d9] text-sm font-semibold tracking-tight text-white">
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
          aria-label="How to use"
          aria-expanded={isHelpOpen}
          onClick={() => setIsHelpOpen(true)}
          className="rounded-full p-2 text-slate-400 transition-colors hover:bg-[#25222f] hover:text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7656f5]"
        >
          <HelpCircle className="h-5 w-5" strokeWidth={1.75} />
        </button>
      </header>

      {isHelpOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-5"
          role="presentation"
          onMouseDown={() => setIsHelpOpen(false)}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="how-to-use-title"
            className="max-h-[calc(100dvh-2.5rem)] w-full max-w-xl overflow-y-auto rounded-2xl border border-[#3a3745] bg-[#1b1921] p-6 shadow-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-[#a995ff]">TurnB PPT Agent</p>
                <h2 id="how-to-use-title" className="mt-1 text-xl font-semibold text-slate-100">
                  How to use
                </h2>
              </div>
              <button
                type="button"
                aria-label="Close help"
                onClick={() => setIsHelpOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-[#2a2732] hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7656f5]"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-5 space-y-5 text-sm leading-6 text-slate-300">
              <section>
                <h3 className="font-semibold text-slate-100">Create a case study deck</h3>
                <ol className="mt-2 list-decimal space-y-1.5 pl-5">
                  <li>Add the project details, either by typing or uploading a file.</li>
                  <li>Answer the agent&apos;s follow-up questions to fill any content gaps.</li>
                  <li>Review the suggested story, then generate and download your PowerPoint.</li>
                </ol>
              </section>

              <section>
                <h3 className="font-semibold text-slate-100">What you can add</h3>
                <p className="mt-1.5">
                  Paste notes, a project brief, client context, problem, solution, delivery approach, outcomes, metrics, and quotes. You can also upload <span className="font-medium text-slate-100">TXT, DOCX, PDF, or PPTX</span> files using the <span className="font-medium text-slate-100">+</span> button.
                </p>
              </section>

              <section>
                <h3 className="font-semibold text-slate-100">Buttons and controls</h3>
                <dl className="mt-2 space-y-2.5">
                  <div>
                    <dt className="font-medium text-slate-100">+ Upload</dt>
                    <dd>Attach one of the supported source files above.</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-slate-100">Message box and arrow</dt>
                    <dd>Type a message, then select the arrow or press Enter to send. Press Shift + Enter for a new line.</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-slate-100">Review Content</dt>
                    <dd>Checks the case study for strong sections, missing details, and questions to answer.</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-slate-100">Generate PPT</dt>
                    <dd>Creates the presentation when your content is ready.</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-slate-100">Generate Anyway</dt>
                    <dd>Creates a deck using the information available now, even if the review identifies gaps.</dd>
                  </div>
                  <div>
                    <dt className="font-medium text-slate-100">Clear Chat</dt>
                    <dd>Removes the current conversation so you can begin a new case study.</dd>
                  </div>
                </dl>
              </section>

              <p className="border-l-2 border-[#7656f5] bg-[#211e2a] px-3 py-2 text-slate-200">
                When the deck is complete, select <span className="font-semibold">Download PowerPoint</span> in the chat to save it.
              </p>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
