"use client";

import React, { useState, useEffect } from "react";
import { Clock } from "lucide-react";
import { getCurrentVietnamTimeParts } from "@/lib/dateUtils";

export const LiveClock: React.FC = () => {
  const [timeParts, setTimeParts] = useState(getCurrentVietnamTimeParts);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const timer = setInterval(() => {
      setTimeParts(getCurrentVietnamTimeParts());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  if (!mounted) {
    return (
      <div className="flex items-center gap-1.5 text-slate-300 text-[11px] font-mono">
        <Clock className="w-3 h-3 text-cyan-400" />
        <span>--:--:-- GMT+7</span>
      </div>
    );
  }

  return (
    <div
      className="inline-flex items-center gap-1.5 text-slate-300 text-[11px] font-mono select-none"
      title="Bộ giờ chuẩn thời gian thực Việt Nam (Asia/Ho_Chi_Minh - GMT+7)"
    >
      <div className="relative flex items-center">
        <Clock className="w-3 h-3 text-cyan-400" />
        <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
      </div>
      <span className="font-bold text-white tracking-wider">{timeParts.timeStr}</span>
      <span className="text-slate-400 hidden xl:inline">
        • {timeParts.dateStr}
      </span>
      <span className="px-1 py-0.2 rounded text-[9px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-800/80">
        VN (GMT+7)
      </span>
    </div>
  );
};
