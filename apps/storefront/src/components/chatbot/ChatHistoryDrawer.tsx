"use client";

import React, { useState } from "react";
import {
  MessageSquare,
  Plus,
  Trash2,
  Edit2,
  X,
  Search,
  Clock,
  Check,
  AlertCircle,
  ExternalLink,
} from "lucide-react";
import { ChatConversation } from "@/lib/chatbot/types";
import {
  groupConversationsByDate,
  searchConversations,
} from "@/lib/chatbot/conversation-storage";

interface ChatHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  conversations: ChatConversation[];
  activeConversationId: string;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onRenameConversation: (id: string, newTitle: string) => void;
  onDeleteConversation: (id: string) => void;
  onClearAll: () => void;
  isLoggedIn?: boolean;
}

export const ChatHistoryDrawer: React.FC<ChatHistoryDrawerProps> = ({
  isOpen,
  onClose,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onRenameConversation,
  onDeleteConversation,
  onClearAll,
  isLoggedIn = false,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  if (!isOpen) return null;

  const filtered = searchConversations(conversations, searchQuery);
  const grouped = groupConversationsByDate(filtered);

  const startRename = (conv: ChatConversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title);
  };

  const saveRename = (id: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (editTitle.trim()) {
      onRenameConversation(id, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm("Bạn có chắc chắn muốn xóa cuộc trò chuyện này?")) {
      onDeleteConversation(id);
    }
  };

  return (
    <div className="absolute inset-0 z-30 bg-white/95 backdrop-blur-sm flex flex-col animate-in fade-in duration-150">
      {/* Header Drawer */}
      <div className="px-3.5 py-3 border-b border-slate-200/90 flex items-center justify-between bg-slate-50/80">
        <div className="flex items-center gap-1.5 font-bold text-xs text-slate-800">
          <Clock className="w-3.5 h-3.5 text-brand-blue-600" />
          <span>Lịch sử trò chuyện</span>
          <span className="text-[10px] text-slate-400 font-normal">
            ({conversations.length})
          </span>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onNewConversation}
            className="px-2 py-1 rounded-lg bg-brand-blue-600 hover:bg-brand-blue-700 text-white text-[11px] font-bold flex items-center gap-1 transition-colors shadow-2xs"
            title="Tạo cuộc trò chuyện mới"
          >
            <Plus className="w-3 h-3" />
            <span>Đoạn chat mới</span>
          </button>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 transition-colors"
            title="Đóng lịch sử"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Thanh tìm kiếm */}
      <div className="p-2.5 border-b border-slate-100 bg-white">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm theo tiêu đề hoặc nội dung..."
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-brand-blue-500 focus:bg-white focus:ring-1 focus:ring-brand-blue-200 transition-all placeholder:text-slate-400"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      {/* Danh sách phân nhóm theo mốc thời gian */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-3.5">
        {Object.keys(grouped).length === 0 ? (
          <div className="py-10 text-center text-xs text-slate-400">
            {searchQuery ? (
              <p>Không tìm thấy cuộc trò chuyện nào phù hợp với &ldquo;{searchQuery}&rdquo;</p>
            ) : (
              <div className="space-y-1.5">
                <MessageSquare className="w-8 h-8 text-slate-300 mx-auto" />
                <p className="font-medium text-slate-600">Chưa có lịch sử hội thoại</p>
                <p className="text-[11px] text-slate-400">
                  Các cuộc trò chuyện của bạn với Trợ lý AI sẽ được lưu trữ tại đây.
                </p>
              </div>
            )}
          </div>
        ) : (
          Object.entries(grouped).map(([groupTitle, list]) => (
            <div key={groupTitle} className="space-y-1">
              <div className="px-2 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
                {groupTitle}
              </div>

              <div className="space-y-1">
                {list.map((conv) => {
                  const isActive = conv.id === activeConversationId;
                  const isEditing = editingId === conv.id;
                  const lastMsg = conv.messages[conv.messages.length - 1];

                  return (
                    <div
                      key={conv.id}
                      onClick={() => {
                        if (!isEditing) {
                          onSelectConversation(conv.id);
                          onClose();
                        }
                      }}
                      className={`group relative p-2 rounded-xl text-xs cursor-pointer transition-all border ${
                        isActive
                          ? "bg-brand-blue-50/80 border-brand-blue-200 text-brand-blue-900 shadow-2xs"
                          : "bg-white hover:bg-slate-50 border-transparent hover:border-slate-200 text-slate-700"
                      }`}
                    >
                      {isEditing ? (
                        <form
                          onSubmit={(e) => saveRename(conv.id, e)}
                          className="flex items-center gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="text"
                            value={editTitle}
                            autoFocus
                            onChange={(e) => setEditTitle(e.target.value)}
                            onBlur={() => saveRename(conv.id)}
                            className="flex-1 px-1.5 py-0.5 text-xs bg-white border border-brand-blue-400 rounded outline-none"
                          />
                          <button
                            type="submit"
                            className="p-1 text-emerald-600 hover:text-emerald-700"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        </form>
                      ) : (
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="font-semibold truncate text-[11.5px] leading-snug">
                              {conv.title}
                            </p>
                            {lastMsg && (
                              <p className="text-[10px] text-slate-400 truncate mt-0.5 font-normal">
                                {lastMsg.content.slice(0, 50)}
                              </p>
                            )}
                          </div>

                          {/* Các nút sửa / xóa trên hover */}
                          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              type="button"
                              onClick={(e) => startRename(conv, e)}
                              className="p-1 rounded text-slate-400 hover:text-brand-blue-600 hover:bg-white transition-colors"
                              title="Đổi tên đoạn chat"
                            >
                              <Edit2 className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => handleDelete(conv.id, e)}
                              className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-white transition-colors"
                              title="Xóa đoạn chat này"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Footer: Thông báo đồng bộ & Nút xóa toàn bộ */}
      <div className="p-2.5 border-t border-slate-200/90 bg-slate-50/80 flex items-center justify-between text-[11px]">
        {showClearConfirm ? (
          <div className="w-full flex items-center justify-between bg-rose-50 border border-rose-200 p-1.5 rounded-lg text-rose-700">
            <span className="font-bold text-[10px]">Xóa toàn bộ lịch sử?</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => {
                  onClearAll();
                  setShowClearConfirm(false);
                }}
                className="px-2 py-0.5 rounded bg-rose-600 text-white font-bold text-[10px] hover:bg-rose-700"
              >
                Xóa hết
              </button>
              <button
                type="button"
                onClick={() => setShowClearConfirm(false)}
                className="px-1.5 py-0.5 text-slate-500 hover:text-slate-800 text-[10px]"
              >
                Hủy
              </button>
            </div>
          </div>
        ) : (
          <>
            <span className="text-[10px] text-slate-400">
              {isLoggedIn ? "Đã đồng bộ tài khoản" : "Lưu trữ trên trình duyệt này"}
            </span>

            {conversations.length > 0 && (
              <button
                type="button"
                onClick={() => setShowClearConfirm(true)}
                className="text-[10px] text-slate-400 hover:text-rose-600 flex items-center gap-1 font-medium transition-colors"
              >
                <Trash2 className="w-3 h-3" />
                <span>Xóa tất cả</span>
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
};
