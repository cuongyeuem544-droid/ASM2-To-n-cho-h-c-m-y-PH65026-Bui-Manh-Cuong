"use client";

import React from "react";
import Link from "next/link";
import { cleanMedicalText } from "@/lib/chatbot/sanitizer";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

/**
 * Bộ dựng Markdown an toàn, tối giản, bảo vệ tiếng Việt và ngăn chặn XSS / HTML thô
 */
export const MarkdownContent: React.FC<MarkdownContentProps> = ({ content, className = "" }) => {
  if (!content) return null;

  // 1. Tiền xử lý: Khử toàn bộ mã escape lỗi (u003c, u003e, u0026...) và HTML rác
  const cleanSource = cleanMedicalText(content);

  // 2. Tách văn bản thành các dòng
  const lines = cleanSource.split("\n");
  const renderedElements: React.ReactNode[] = [];

  let inList = false;
  let listItems: React.ReactNode[] = [];
  let isNumberedList = false;

  const flushList = () => {
    if (inList && listItems.length > 0) {
      if (isNumberedList) {
        renderedElements.push(
          <ol key={`ol-${renderedElements.length}`} className="list-decimal pl-5 space-y-1 my-2">
            {listItems}
          </ol>
        );
      } else {
        renderedElements.push(
          <ul key={`ul-${renderedElements.length}`} className="list-disc pl-5 space-y-1 my-2">
            {listItems}
          </ul>
        );
      }
      listItems = [];
      inList = false;
    }
  };

  /**
   * Parse inline formatting: **bold**, *italic*, `code`, [text](url)
   */
  const parseInline = (text: string): React.ReactNode => {
    const regex = /(\[.*?\]\(.*?\)|\*\*.*?\*\*|\*.*?\*|`.*?`)/g;
    const parts = text.split(regex);

    return parts.map((part, index) => {
      if (part.startsWith("[") && part.includes("](") && part.endsWith(")")) {
        const match = part.match(/\[(.*?)\]\((.*?)\)/);
        if (match) {
          const [, label, url] = match;
          const isInternal = url.startsWith("/");
          if (isInternal) {
            return (
              <Link
                key={index}
                href={url}
                className="text-brand-blue-600 font-semibold hover:underline decoration-brand-blue-400"
              >
                {label}
              </Link>
            );
          }
          return (
            <a
              key={index}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand-blue-600 font-semibold hover:underline decoration-brand-blue-400"
            >
              {label}
            </a>
          );
        }
      }

      if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
        return (
          <strong key={index} className="font-bold text-slate-900">
            {part.slice(2, -2)}
          </strong>
        );
      }

      if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
        return (
          <em key={index} className="italic text-slate-700">
            {part.slice(1, -1)}
          </em>
        );
      }

      if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
        return (
          <code
            key={index}
            className="px-1.5 py-0.5 rounded-md bg-slate-100 text-brand-blue-700 font-mono text-[11px] font-medium border border-slate-200"
          >
            {part.slice(1, -1)}
          </code>
        );
      }

      return part;
    });
  };

  lines.forEach((line, lineIdx) => {
    const trimmed = line.trim();

    // Dòng trống
    if (!trimmed) {
      flushList();
      renderedElements.push(<div key={`br-${lineIdx}`} className="h-1.5" />);
      return;
    }

    // Tiêu đề H3 / H4
    if (trimmed.startsWith("### ")) {
      flushList();
      renderedElements.push(
        <h3
          key={`h3-${lineIdx}`}
          className="text-sm font-bold text-slate-900 mt-2.5 mb-1 flex items-center gap-1.5"
        >
          {parseInline(trimmed.slice(4))}
        </h3>
      );
      return;
    }

    if (trimmed.startsWith("## ")) {
      flushList();
      renderedElements.push(
        <h2
          key={`h2-${lineIdx}`}
          className="text-sm font-extrabold text-slate-900 mt-2.5 mb-1.5"
        >
          {parseInline(trimmed.slice(3))}
        </h2>
      );
      return;
    }

    if (trimmed.startsWith("# ")) {
      flushList();
      renderedElements.push(
        <h1
          key={`h1-${lineIdx}`}
          className="text-base font-extrabold text-slate-900 mt-3 mb-2"
        >
          {parseInline(trimmed.slice(2))}
        </h1>
      );
      return;
    }

    // Blockquote
    if (trimmed.startsWith("> ")) {
      flushList();
      renderedElements.push(
        <blockquote
          key={`quote-${lineIdx}`}
          className="pl-3 py-1 my-2 border-l-2 border-brand-blue-500 bg-brand-blue-50/50 text-xs text-slate-700 italic rounded-r-md"
        >
          {parseInline(trimmed.slice(2))}
        </blockquote>
      );
      return;
    }

    // Danh sách không thứ tự: "-", "*", "•"
    if (/^[-*•]\s+/.test(trimmed)) {
      const itemText = trimmed.replace(/^[-*•]\s+/, "");
      if (!inList || isNumberedList) {
        flushList();
        inList = true;
        isNumberedList = false;
      }
      listItems.push(
        <li key={`li-${lineIdx}`} className="text-xs leading-relaxed text-slate-700">
          {parseInline(itemText)}
        </li>
      );
      return;
    }

    // Danh sách có thứ tự: "1. ", "2. "
    if (/^\d+\.\s+/.test(trimmed)) {
      const itemText = trimmed.replace(/^\d+\.\s+/, "");
      if (!inList || !isNumberedList) {
        flushList();
        inList = true;
        isNumberedList = true;
      }
      listItems.push(
        <li key={`oli-${lineIdx}`} className="text-xs leading-relaxed text-slate-700">
          {parseInline(itemText)}
        </li>
      );
      return;
    }

    // Đoạn văn bản thông thường
    flushList();
    renderedElements.push(
      <p key={`p-${lineIdx}`} className="text-xs leading-relaxed text-slate-700 my-0.5">
        {parseInline(trimmed)}
      </p>
    );
  });

  flushList();

  return <div className={`space-y-0.5 text-xs ${className}`}>{renderedElements}</div>;
};
