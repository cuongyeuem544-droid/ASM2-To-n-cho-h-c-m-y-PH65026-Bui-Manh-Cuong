"use client";

import React from "react";
import { Sparkles } from "lucide-react";

interface QuickReplyChipsProps {
  chips?: string[];
  onSelect: (text: string) => void;
  disabled?: boolean;
}

export const QuickReplyChips: React.FC<QuickReplyChipsProps> = ({
  chips,
  onSelect,
  disabled = false,
}) => {
  if (!chips || chips.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 pt-1.5 pb-0.5">
      {chips.map((chip, idx) => (
        <button
          key={idx}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(chip)}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-brand-blue-50/80 text-brand-blue-700 hover:bg-brand-blue-600 hover:text-white border border-brand-blue-200/80 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs active:scale-95"
        >
          <Sparkles className="w-2.5 h-2.5 opacity-70 shrink-0" />
          <span className="truncate max-w-[240px]">{chip}</span>
        </button>
      ))}
    </div>
  );
};
