"use client";

import { ArrowUp, Plus } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { ACCEPTED_FILE_TYPES } from "@/lib/constants";

const MIN_INPUT_HEIGHT_PX = 40;
const MAX_INPUT_HEIGHT_PX = 320;

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onUpload: (file: File) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  onUpload,
  disabled,
  placeholder = "Message TurnB PPT Agent...",
}: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const syncTextareaHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const next = Math.min(
      Math.max(el.scrollHeight, MIN_INPUT_HEIGHT_PX),
      MAX_INPUT_HEIGHT_PX,
    );
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > MAX_INPUT_HEIGHT_PX ? "auto" : "hidden";
  }, []);

  useEffect(() => {
    syncTextareaHeight();
  }, [value, syncTextareaHeight]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim()) onSend();
    }
  };

  return (
    <div className="shrink-0 border-t border-[#2a3140] bg-[#12151c] px-4 py-4 md:px-10 lg:px-16">
      <div className="w-full">
      <div className="flex items-end gap-2 rounded-[1.75rem] border border-[#2f3848] bg-[#141820] px-2 py-2 shadow-inner">
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_FILE_TYPES}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onUpload(file);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          aria-label="Upload file"
          disabled={disabled}
          onClick={() => fileInputRef.current?.click()}
          className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[#3d4f6f] text-slate-300 transition-colors hover:bg-[#1e2533] hover:text-slate-100 disabled:opacity-50"
        >
          <Plus className="h-5 w-5" strokeWidth={1.75} />
        </button>

        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="min-h-[2.5rem] flex-1 resize-none overflow-hidden bg-transparent py-2.5 text-[0.95rem] leading-relaxed text-slate-200 placeholder:text-slate-500 focus:outline-none disabled:opacity-50"
        />

        <button
          type="button"
          aria-label="Send message"
          disabled={disabled || !value.trim()}
          onClick={onSend}
          className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[#111318] transition-opacity hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ArrowUp className="h-5 w-5" strokeWidth={2} />
        </button>
      </div>
      </div>
    </div>
  );
}
