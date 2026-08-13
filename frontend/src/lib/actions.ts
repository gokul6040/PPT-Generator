/**
 * Canonical user messages — must match Streamlit / agent_controller routing.
 * @see src/readiness.py is_explicit_review_request
 * @see src/agent_controller.py generate intent ("Generate", "Generate anyway")
 */
export const CHAT_ACTIONS = {
  REVIEW: "Review content",
  GENERATE: "Generate",
  GENERATE_ANYWAY: "Generate anyway",
} as const;

export type ChatActionKey = keyof typeof CHAT_ACTIONS;

export const ACTION_LABELS: Record<ChatActionKey, string> = {
  REVIEW: "Review Content",
  GENERATE: "Generate PPT",
  GENERATE_ANYWAY: "Generate Anyway",
};
