"use client";

import { useEffect, useRef } from "react";
import { ActionChips } from "./ActionChips";
import { ChatInput } from "./ChatInput";
import { ChatMessageBubble } from "./ChatMessage";
import { Header } from "./Header";
import { useChat } from "@/hooks/useChat";

export function ChatApp() {
  const {
    messages,
    input,
    setInput,
    isLoading,
    error,
    showActionChips,
    sendUserMessage,
    runAction,
    clearChat,
    handleFileUpload,
    sessionId,
  } = useChat();

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, isLoading, showActionChips]);

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-[#0c0e12]">
      <Header />

      <div ref={scrollRef} className="flex-1 overflow-y-auto bg-[#12151c] px-6 py-5 md:px-10 lg:px-16">
        <div className="w-full space-y-6">
            {messages.map((message) => (
              <ChatMessageBubble
                key={message.id}
                message={message}
                sessionId={sessionId}
              />
            ))}

            {isLoading && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#3d4f6f] bg-[#1a2030] text-[10px] font-semibold text-slate-200">
                  TB
                </div>
                <div className="rounded-2xl rounded-bl-md border border-[#2a3140] bg-[#1c212b] px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-slate-500" />
                    <span className="h-2 w-2 animate-pulse rounded-full bg-slate-500 [animation-delay:150ms]" />
                    <span className="h-2 w-2 animate-pulse rounded-full bg-slate-500 [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}

            {showActionChips && (
              <ActionChips
                onAction={runAction}
                onClear={clearChat}
                disabled={isLoading}
              />
            )}

            {error && (
              <p className="text-center text-sm text-red-400/90">{error}</p>
            )}
        </div>
      </div>

      <ChatInput
        value={input}
        onChange={setInput}
        onSend={sendUserMessage}
        onUpload={handleFileUpload}
        disabled={isLoading}
      />
    </div>
  );
}
