import { CheckCheck, Download } from "lucide-react";
import { downloadPpt, downloadUrl } from "@/lib/api";
import type { ChatMessage, ReviewPayload } from "@/lib/types";

function splitReviewItems(items: string[] | undefined): string[] {
  if (!items?.length) return [];
  const result: string[] = [];
  for (const item of items) {
    const text = String(item).trim();
    if (!text) continue;
    if (text.includes(" - ")) {
      result.push(...text.split(/\s+-\s+/).map((p) => p.trim()).filter(Boolean));
    } else {
      result.push(text);
    }
  }
  return result;
}

function ReviewCard({ review }: { review: ReviewPayload }) {
  const coverage = review.section_coverage || review.section_status || {};
  const titleStatus = (review.title_status || "").toLowerCase();
  const labels: Record<string, string> = {
    problem_statement: "Problem",
    design_implementation: "Design",
    impact: "Impact",
  };

  return (
    <div className="mt-3 space-y-4 border-t border-[#383543] pt-3 text-sm">
      <p className="font-medium text-slate-200">
        I&apos;ve reviewed your content. Here is what I found:
      </p>

      {(titleStatus || Object.keys(coverage).length > 0) && (
        <div className="text-xs text-slate-400">
          {titleStatus && (
            <span className="mr-3">
              <strong className="text-slate-300">Title:</strong> {titleStatus}
            </span>
          )}
          {Object.entries(labels).map(([key, short]) => (
            <span key={key} className="mr-3">
              <strong className="text-slate-300">{short}:</strong>{" "}
              {(coverage[key] || "weak").toString()}
            </span>
          ))}
        </div>
      )}

      <ReviewSection
        title="Available / Strong"
        items={splitReviewItems(review.available_strong)}
      />
      <ReviewSection
        title="Missing / Weak"
        items={splitReviewItems(review.missing_weak)}
      />
      {!!review.questions_to_user?.length && (
        <ReviewSection
          title="Questions"
          items={splitReviewItems(review.questions_to_user)}
        />
      )}
      {review.impact_note && (
        <div className="border-l-2 border-[#7656f5] bg-[#1b1922] px-3 py-2 text-slate-300">
          <strong className="text-[#a793ff]">Impact note:</strong>{" "}
          {review.impact_note}
        </div>
      )}
    </div>
  );
}

function ReviewSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <div className="mb-2 inline-block rounded-md border border-[#454052] bg-[#24203a] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-200">
        {title}
      </div>
      {items.length ? (
        <ul className="list-disc space-y-1.5 pl-5 text-slate-300">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-slate-500 italic">None identified.</p>
      )}
    </div>
  );
}

function formatContent(content: string) {
  const parts = content.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-medium text-slate-100">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return part;
  });
}

interface ChatMessageProps {
  message: ChatMessage;
  sessionId: string | null;
}

export function ChatMessageBubble({ message, sessionId }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isReview = message.msg_type === "review" && message.review;

  const handleDownload = async () => {
    if (!sessionId || !message.download_blob) return;
    try {
      const blob = await downloadPpt(sessionId, message.download_blob);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = message.download_file_name || "turnb_case_study.pptx";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      if (message.download_blob) {
        window.open(downloadUrl(sessionId, message.download_blob), "_blank");
      }
    }
  };

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {!isUser && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#454052] bg-[#1b1922] text-[10px] font-semibold text-slate-200">
          TB
        </div>
      )}

      <div
        className={`max-w-[min(72rem,85%)] ${isUser ? "items-end" : "items-start"} flex flex-col`}
      >
        <div
          className={`rounded-2xl px-4 py-3 text-[0.925rem] leading-relaxed ${
            isUser
              ? "rounded-br-md bg-[#292531] text-slate-100"
              : "rounded-bl-md border border-[#302e3a] bg-[#1a1920] text-slate-300"
          }`}
        >
          {!isReview && (
            <p className="whitespace-pre-wrap">{formatContent(message.content)}</p>
          )}
          {isReview && message.review && <ReviewCard review={message.review} />}
          {message.download_blob && sessionId && (
            <button
              type="button"
              onClick={() => void handleDownload()}
              className="mt-3 inline-flex items-center gap-2 rounded-lg border border-[#454052] bg-[#24203a] px-3 py-2 text-sm text-slate-200 transition-colors hover:bg-[#302a4b]"
            >
              <Download className="h-4 w-4" strokeWidth={1.75} />
              Download PowerPoint
            </button>
          )}
        </div>
        <div
          className={`mt-1.5 flex items-center gap-1.5 text-xs text-slate-500 ${
            isUser ? "flex-row-reverse" : ""
          }`}
        >
          <span>{message.timestamp}</span>
          {isUser && (
            <CheckCheck className="h-3.5 w-3.5 text-[#967dff]" strokeWidth={1.75} />
          )}
        </div>
      </div>
    </div>
  );
}
