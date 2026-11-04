"use client";

import React from "react";

interface MarkdownViewProps {
  content: string;
  className?: string;
}

/**
 * Format inline markdown tokens: bold (**text**), italic (*text*), inline code (`code`).
 */
function renderInlineMarkdown(text: string): React.ReactNode[] {
  // Regex to split by bold (**...**), code (`...`), or italic (*...*)
  const tokens = text.split(/(\*\*[^*]+?\*\*|`[^`]+?`|\*[^*]+?\*)/g);

  return tokens.map((token, idx) => {
    if (!token) return null;

    if (token.startsWith("**") && token.endsWith("**") && token.length >= 4) {
      return (
        <strong key={idx} className="font-bold text-[#ffffff]">
          {token.slice(2, -2)}
        </strong>
      );
    }
    if (token.startsWith("`") && token.endsWith("`") && token.length >= 2) {
      return (
        <code
          key={idx}
          className="rounded bg-[#161a26] border border-[#2d3748] px-1 py-0.5 font-mono text-[10px] text-[#ffe600]"
        >
          {token.slice(1, -1)}
        </code>
      );
    }
    if (token.startsWith("*") && token.endsWith("*") && token.length >= 2) {
      return (
        <em key={idx} className="italic text-[#d1d5db]">
          {token.slice(1, -1)}
        </em>
      );
    }
    return <span key={idx}>{token}</span>;
  });
}

/**
 * Lightweight, accessible Markdown renderer for AI chat messages and direction summaries.
 */
export function MarkdownView({ content, className = "" }: MarkdownViewProps) {
  if (!content) return null;

  // Split into paragraphs / blocks
  const blocks = content.split(/\n{2,}/);

  return (
    <div className={`space-y-2 text-xs leading-relaxed ${className}`}>
      {blocks.map((block, blockIdx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        const lines = trimmed.split("\n");

        // 1. Heading 3: ### ...
        if (trimmed.startsWith("### ")) {
          return (
            <h4 key={blockIdx} className="font-bold text-sm text-[#ffffff] pt-1 pb-0.5">
              {renderInlineMarkdown(trimmed.slice(4))}
            </h4>
          );
        }

        // 2. Heading 2: ## ...
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={blockIdx} className="font-bold text-base text-[#ffffff] pt-1.5 pb-0.5">
              {renderInlineMarkdown(trimmed.slice(3))}
            </h3>
          );
        }

        // 3. Bullet list (lines start with •, -, or *)
        const isBulletList = lines.every(
          (l) =>
            l.trim().startsWith("• ") ||
            l.trim().startsWith("- ") ||
            l.trim().startsWith("* ") ||
            l.trim() === "",
        );

        if (isBulletList && lines.length > 0) {
          return (
            <ul key={blockIdx} className="space-y-1 pl-1 text-[#e5e7eb]">
              {lines.map((l, lIdx) => {
                const itemText = l.trim().replace(/^[•\-*]\s*/, "");
                if (!itemText) return null;
                return (
                  <li key={lIdx} className="flex items-start gap-1.5">
                    <span className="text-[#ffe600] select-none text-[11px] leading-5">•</span>
                    <span className="flex-1 leading-5">{renderInlineMarkdown(itemText)}</span>
                  </li>
                );
              })}
            </ul>
          );
        }

        // 4. Numbered list (lines start with 1. , 2. )
        const isNumberedList = lines.every(
          (l) => /^\d+\.\s+/.test(l.trim()) || l.trim() === "",
        );

        if (isNumberedList && lines.length > 0) {
          return (
            <ol key={blockIdx} className="space-y-1 pl-1 text-[#e5e7eb]">
              {lines.map((l, lIdx) => {
                const match = l.trim().match(/^(\d+)\.\s+(.*)$/);
                if (!match) return null;
                const num = match[1];
                const itemText = match[2];
                return (
                  <li key={lIdx} className="flex items-start gap-1.5">
                    <span className="font-mono text-[#ffe600] font-bold select-none text-[11px] leading-5">
                      {num}.
                    </span>
                    <span className="flex-1 leading-5">{renderInlineMarkdown(itemText)}</span>
                  </li>
                );
              })}
            </ol>
          );
        }

        // 5. Standard paragraph with single line-break handling
        return (
          <p key={blockIdx} className="text-[#e5e7eb]">
            {lines.map((line, lineIdx) => (
              <React.Fragment key={lineIdx}>
                {renderInlineMarkdown(line)}
                {lineIdx < lines.length - 1 && <br />}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}

