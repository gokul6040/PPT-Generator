import type { ChatMessage } from "./types";

export const WELCOME_MESSAGE =
  "Upload a file or paste your project details. I'll review the content, identify missing information, and generate a presentation when ready.";

/** Demo conversation — not used on initial load; for Storybook/tests only. */
export const SAMPLE_CONVERSATION: ChatMessage[] = [
  {
    id: "seed-1",
    role: "assistant",
    content: WELCOME_MESSAGE,
    timestamp: "10:21 AM",
  },
  {
    id: "seed-2",
    role: "user",
    content:
      "Client had manual Excel reporting across stores and no single trusted inventory view.",
    timestamp: "10:22 AM",
  },
  {
    id: "seed-3",
    role: "assistant",
    content:
      "Problem Statement looks strong. Design details are decent. Impact needs measurable outcomes before final generation.",
    timestamp: "10:23 AM",
  },
];

export const ACCEPTED_FILE_TYPES = ".txt,.docx,.pdf,.pptx";
