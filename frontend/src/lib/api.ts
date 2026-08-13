import type { SessionState } from "./types";

function getApiBase(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  // Empty string = same-origin (unified container / Azure single app)
  if (raw === "") return "";
  if (raw) return raw.replace(/\/$/, "");
  // Local dev: separate API process on 8000
  return "http://localhost:8000";
}

const API_BASE = getApiBase();

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `API error: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function downloadUrl(sessionId: string, blobName: string) {
  const params = new URLSearchParams({
    session_id: sessionId,
    blob_name: blobName,
  });
  return `${API_BASE}/chat/download?${params.toString()}`;
}

export async function createSession(): Promise<SessionState> {
  const res = await fetch(`${API_BASE}/chat/session`, { method: "POST" });
  return parseJson<SessionState>(res);
}

export async function fetchSession(sessionId: string): Promise<SessionState> {
  const res = await fetch(`${API_BASE}/chat/session/${sessionId}`);
  return parseJson<SessionState>(res);
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
): Promise<SessionState> {
  const res = await fetch(`${API_BASE}/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  return parseJson<SessionState>(res);
}

export async function uploadChatFile(
  sessionId: string,
  file: File,
): Promise<SessionState> {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("file", file);
  const res = await fetch(`${API_BASE}/chat/upload`, {
    method: "POST",
    body: form,
  });
  return parseJson<SessionState>(res);
}

export async function clearChatSession(sessionId: string): Promise<SessionState> {
  const res = await fetch(`${API_BASE}/chat/clear`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return parseJson<SessionState>(res);
}

export async function downloadPpt(
  sessionId: string,
  blobName: string,
): Promise<Blob> {
  const res = await fetch(downloadUrl(sessionId, blobName));
  if (!res.ok) throw new Error("Download failed");
  return res.blob();
}
