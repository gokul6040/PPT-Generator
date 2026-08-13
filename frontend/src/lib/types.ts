export type ChatRole = "user" | "assistant";

export type MessageType = "text" | "review";

export type ChatPhase =
  | "start"
  | "collecting"
  | "needs_content"
  | "reviewed"
  | "awaiting_details"
  | "generated"
  | "done";

export interface ReviewPayload {
  section_status?: Record<string, string>;
  section_coverage?: Record<string, string>;
  title_status?: string;
  detected_title?: string;
  available_strong?: string[];
  missing_weak?: string[];
  questions_to_user?: string[];
  impact_note?: string;
  can_continue?: boolean;
  readiness?: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  msg_type?: MessageType;
  review?: ReviewPayload;
  download_blob?: string;
  download_file_name?: string;
  download_url?: string;
}

export interface SessionState {
  session_id: string;
  phase: ChatPhase;
  combined_content: string;
  review_result: ReviewPayload | null;
  show_action_buttons: boolean;
  messages: ChatMessage[];
}
