"use client";

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  X,
  Pill,
  Stethoscope,
  ShoppingBag,
  Truck,
  Headphones,
  ChevronRight,
  ArrowLeft,
  Sparkles,
} from "lucide-react";

interface PromptGroup {
  id: string;
  name: string;
  icon: typeof Pill;
  color: string;
  prompts: string[];
}

export const SUGGESTED_PROMPT_GROUPS: PromptGroup[] = [
  {
    id: "drugs",
    name: "Thông tin thuốc",
    icon: Pill,
    color: "from-blue-500 to-cyan-500",
    prompts: [
      "Tra cứu Panadol Extra",
      "Paracetamol có công dụng gì?",
      "Thuốc này có tác dụng phụ không?",
      "Cần lưu ý gì khi sử dụng thuốc?",
      "Thuốc này có phải thuốc kê đơn không?",
      "Tôi muốn tìm hiểu thành phần thuốc.",
    ],
  },
  {
    id: "health",
    name: "Tư vấn sức khỏe",
    icon: Stethoscope,
    color: "from-emerald-500 to-teal-500",
    prompts: [
      "Tôi bị sốt và đau đầu",
      "Tôi bị đau đầu từ hôm qua.",
      "Tôi bị sốt và mệt mỏi.",
      "Tôi bị đau bụng.",
      "Tôi thường xuyên mất ngủ.",
      "Khi nào tôi nên đi khám?",
      "Tôi muốn hỏi về triệu chứng đang gặp.",
    ],
  },
  {
    id: "products",
    name: "Sản phẩm tại H4CARE",
    icon: ShoppingBag,
    color: "from-indigo-500 to-purple-500",
    prompts: [
      "Tìm sản phẩm theo tên.",
      "Kiểm tra giá bán.",
      "Kiểm tra tình trạng còn hàng.",
      "Xem thành phần sản phẩm.",
      "Tìm sản phẩm theo danh mục.",
    ],
  },
  {
    id: "orders",
    name: "Đơn hàng & chính sách",
    icon: Truck,
    color: "from-amber-500 to-orange-500",
    prompts: [
      "Chính sách đổi trả thuốc thế nào?",
      "Kiểm tra đơn hàng của tôi.",
      "Phí vận chuyển bao nhiêu?",
      "Thời gian giao hàng dự kiến?",
      "Tôi muốn được hỗ trợ đơn hàng.",
    ],
  },
  {
    id: "human",
    name: "Tư vấn trực tiếp",
    icon: Headphones,
    color: "from-rose-500 to-pink-500",
    prompts: [
      "Tôi muốn gặp nhân viên tư vấn",
      "Tôi cần trao đổi với dược sĩ.",
      "Tôi muốn được hỗ trợ trực tiếp.",
      "Tôi cần tư vấn về đơn hàng.",
    ],
  },
];

interface SuggestedPromptsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectPrompt: (prompt: string) => void;
  onRequestLiveChat?: () => void;
}

export const SuggestedPromptsModal: React.FC<SuggestedPromptsModalProps> = ({
  isOpen,
  onClose,
  onSelectPrompt,
  onRequestLiveChat,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);

  const filteredGroups = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) {
      if (selectedGroupId) {
        return SUGGESTED_PROMPT_GROUPS.filter((g) => g.id === selectedGroupId);
      }
      return SUGGESTED_PROMPT_GROUPS;
    }

    return SUGGESTED_PROMPT_GROUPS.map((group) => {
      const matchedPrompts = group.prompts.filter(
        (p) => p.toLowerCase().includes(q) || group.name.toLowerCase().includes(q)
      );
      return {
        ...group,
        prompts: matchedPrompts,
      };
    }).filter((g) => g.prompts.length > 0);
  }, [searchQuery, selectedGroupId]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[110] flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-900/50 backdrop-blur-xs">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 40 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
          className="relative w-full sm:max-w-md max-h-[85vh] bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl border border-slate-100 flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-brand-blue-50/60 to-white">
            <div className="flex items-center gap-2">
              {selectedGroupId && (
                <button
                  type="button"
                  onClick={() => setSelectedGroupId(null)}
                  className="p-1 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
                  title="Quay lại tất cả"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>
              )}
              <div className="w-8 h-8 rounded-xl bg-brand-blue-600 text-white flex items-center justify-center shadow-xs">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-800">Từ khóa & Câu hỏi gợi ý</h3>
                <p className="text-[11px] text-slate-400">Chọn câu hỏi để điền nhanh vào ô chat</p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              aria-label="Đóng"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Search bar */}
          <div className="p-3 border-b border-slate-100 bg-slate-50/70">
            <div className="relative flex items-center">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Tìm câu hỏi gợi ý nhanh..."
                className="w-full pl-9 pr-8 py-2 text-xs bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-500 text-slate-800 placeholder:text-slate-400"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 p-1 text-slate-400 hover:text-slate-600"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Category pills */}
            {!searchQuery && (
              <div className="flex items-center gap-1.5 mt-2.5 overflow-x-auto scrollbar-none pb-0.5">
                <button
                  type="button"
                  onClick={() => setSelectedGroupId(null)}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-medium shrink-0 transition-colors ${
                    selectedGroupId === null
                      ? "bg-brand-blue-600 text-white shadow-2xs"
                      : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  Tất cả ({SUGGESTED_PROMPT_GROUPS.reduce((acc, g) => acc + g.prompts.length, 0)})
                </button>
                {SUGGESTED_PROMPT_GROUPS.map((g) => (
                  <button
                    key={g.id}
                    type="button"
                    onClick={() => setSelectedGroupId(g.id)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-medium shrink-0 transition-colors ${
                      selectedGroupId === g.id
                        ? "bg-brand-blue-600 text-white shadow-2xs"
                        : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-100"
                    }`}
                  >
                    {g.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* List of prompts */}
          <div className="flex-1 overflow-y-auto p-3 space-y-4 max-h-[50vh] sm:max-h-[380px]">
            {filteredGroups.length === 0 ? (
              <div className="py-8 text-center text-slate-400 text-xs">
                Không tìm thấy câu hỏi gợi ý phù hợp với từ khóa &ldquo;{searchQuery}&rdquo;.
              </div>
            ) : (
              filteredGroups.map((group) => {
                const IconComponent = group.icon;
                return (
                  <div key={group.id} className="space-y-1.5">
                    <div className="flex items-center gap-1.5 px-1 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                      <div className={`w-4 h-4 rounded-md bg-gradient-to-tr ${group.color} text-white flex items-center justify-center`}>
                        <IconComponent className="w-2.5 h-2.5" />
                      </div>
                      <span>{group.name}</span>
                    </div>

                    <div className="space-y-1">
                      {group.prompts.map((prompt, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            if (group.id === "human" && onRequestLiveChat) {
                              onRequestLiveChat();
                            }
                            onSelectPrompt(prompt);
                            onClose();
                          }}
                          className="w-full text-left p-2.5 rounded-xl bg-slate-50/80 hover:bg-brand-blue-50 border border-slate-100 hover:border-brand-blue-200 text-xs text-slate-700 hover:text-brand-blue-900 transition-all flex items-center justify-between group active:scale-[0.99]"
                        >
                          <span className="font-medium leading-relaxed">{prompt}</span>
                          <ChevronRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-brand-blue-500 transition-colors shrink-0 ml-2" />
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer notice */}
          <div className="p-3 bg-slate-50 border-t border-slate-100 text-[10px] text-slate-400 text-center">
            💡 Nhấn câu hỏi để tự động điền vào ô chat, bạn có thể chỉnh sửa trước khi gửi.
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
