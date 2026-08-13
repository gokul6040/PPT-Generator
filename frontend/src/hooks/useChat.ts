"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CHAT_ACTIONS, type ChatActionKey } from "@/lib/actions";
import {
  clearChatSession,
  createSession,
  fetchSession,
  sendChatMessage,
  uploadChatFile,
} from "@/lib/api";
import type { ChatMessage, SessionState } from "@/lib/types";

const SESSION_STORAGE_KEY = "turnb_ppt_session_id";

function readStoredSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SESSION_STORAGE_KEY);
}

function persistSessionId(sessionId: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

function applySession(state: SessionState) {
  return {
    sessionId: state.session_id,
    messages: state.messages,
    phase: state.phase,
    combinedContent: state.combined_content,
    reviewResult: state.review_result,
    showActionChips: state.show_action_buttons,
  };
}

export function useChat() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [phase, setPhase] = useState<SessionState["phase"]>("start");
  const [combinedContent, setCombinedContent] = useState("");
  const [reviewResult, setReviewResult] = useState<SessionState["review_result"]>(null);
  const [showActionChips, setShowActionChips] = useState(false);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const initRef = useRef(false);

  const syncFromServer = useCallback((state: SessionState) => {
    const next = applySession(state);
    setSessionId(next.sessionId);
    persistSessionId(next.sessionId);
    setMessages(next.messages);
    setPhase(next.phase);
    setCombinedContent(next.combinedContent);
    setReviewResult(next.reviewResult);
    setShowActionChips(next.showActionChips);
  }, []);

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;

    const bootstrap = async () => {
      const storedId = readStoredSessionId();
      if (storedId) {
        try {
          return await fetchSession(storedId);
        } catch {
          // stale id (API restart, expired session) — create fresh
        }
      }
      return createSession();
    };

    bootstrap()
      .then(syncFromServer)
      .catch((err) => {
        const msg = err instanceof Error ? err.message : "Failed to start session.";
        if (msg === "Failed to fetch") {
          setError(
            "Cannot reach the API at http://localhost:8000 — start it with start-api.ps1 or run-dev.ps1.",
          );
        } else {
          setError(msg);
        }
      })
      .finally(() => setIsBootstrapping(false));
  }, [syncFromServer]);

  const runWithSession = useCallback(
    async (fn: (sid: string) => Promise<SessionState>) => {
      if (!sessionId || isLoading) return;
      setError(null);
      setIsLoading(true);
      try {
        const state = await fn(sessionId);
        syncFromServer(state);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, sessionId, syncFromServer],
  );

  const dispatchMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      await runWithSession((sid) => sendChatMessage(sid, trimmed));
    },
    [runWithSession],
  );

  const sendUserMessage = useCallback(() => {
    const text = input;
    setInput("");
    void dispatchMessage(text);
  }, [dispatchMessage, input]);

  const runAction = useCallback(
    (action: ChatActionKey) => {
      void dispatchMessage(CHAT_ACTIONS[action]);
    },
    [dispatchMessage],
  );

  const clearChat = useCallback(() => {
    if (!sessionId) return;
    setError(null);
    setIsLoading(true);
    clearChatSession(sessionId)
      .then(syncFromServer)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not clear chat."),
      )
      .finally(() => setIsLoading(false));
  }, [sessionId, syncFromServer]);

  const handleFileUpload = useCallback(
    async (file: File) => {
      await runWithSession((sid) => uploadChatFile(sid, file));
    },
    [runWithSession],
  );

  return {
    messages,
    phase,
    input,
    setInput,
    isLoading: isLoading || isBootstrapping,
    error,
    showActionChips: showActionChips && !isLoading && !isBootstrapping,
    sessionId,
    sendUserMessage,
    runAction,
    clearChat,
    handleFileUpload,
  };
}
