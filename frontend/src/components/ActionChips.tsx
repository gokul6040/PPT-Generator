import {
  ClipboardCheck,
  LayoutTemplate,
  Play,
  Trash2,
} from "lucide-react";
import { ACTION_LABELS, type ChatActionKey } from "@/lib/actions";

const ACTION_CONFIG: Record<
  ChatActionKey,
  { icon: typeof ClipboardCheck; variant?: "default" | "danger" }
> = {
  REVIEW: { icon: ClipboardCheck },
  GENERATE: { icon: LayoutTemplate },
  GENERATE_ANYWAY: { icon: Play },
};

interface ActionChipsProps {
  onAction: (action: ChatActionKey) => void;
  onClear: () => void;
  disabled?: boolean;
}

export function ActionChips({ onAction, onClear, disabled }: ActionChipsProps) {
  const actions = (Object.keys(ACTION_CONFIG) as ChatActionKey[]).map(
    (key) => ({
      key,
      label: ACTION_LABELS[key],
      icon: ACTION_CONFIG[key].icon,
    }),
  );

  return (
    <div className="flex flex-wrap gap-2 px-1 pt-1">
      {actions.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          type="button"
          disabled={disabled}
          onClick={() => onAction(key)}
          className="inline-flex items-center gap-2 rounded-full border border-[#3a4458] bg-[#171c26] px-3.5 py-2 text-sm text-slate-300 transition-colors hover:border-[#4a6fa5] hover:bg-[#1e2533] hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Icon className="h-4 w-4 text-slate-400" strokeWidth={1.75} />
          {label}
        </button>
      ))}
      <button
        type="button"
        disabled={disabled}
        onClick={onClear}
        className="inline-flex items-center gap-2 rounded-full border border-[#4a3038] bg-[#1a1719] px-3.5 py-2 text-sm text-slate-400 transition-colors hover:border-[#6b4048] hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Trash2 className="h-4 w-4" strokeWidth={1.75} />
        Clear Chat
      </button>
    </div>
  );
}
