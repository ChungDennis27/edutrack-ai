import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import remarkBreaks from "remark-breaks";
import rehypeKatex from "rehype-katex";
import { cn } from "@/lib/utils";

/** Commands that strongly indicate a bare (undelimited) LaTeX expression. */
const MATH_COMMAND =
  /\\(?:frac|sqrt|pm|mp|times|div|cdot|leq|geq|neq|approx|Delta|alpha|beta|gamma|theta|lambda|mu|pi|sigma|omega|sum|prod|int|lim|log|ln|sin|cos|tan|begin|end|overline|vec|binom|left|right|quad|text)\b/;
const SCRIPT = /[\w)\]}]\s*[\^_]/;
const MATH_CHARS = new Set(
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\\{}^_+-*/=()[]<>.,|' \t"
);

function looksLikeMath(run: string): boolean {
  return MATH_COMMAND.test(run) || SCRIPT.test(run);
}

function wrapBareInLine(line: string): string {
  if (line.includes("$")) return line; // already delimited

  let out = "";
  let i = 0;
  while (i < line.length) {
    if (MATH_CHARS.has(line[i])) {
      let j = i;
      while (j < line.length && MATH_CHARS.has(line[j])) j += 1;
      const run = line.slice(i, j);

      if (looksLikeMath(run)) {
        const core = run.trim();
        const lead = run.slice(0, run.length - run.trimStart().length);
        const trail = run.slice(run.trimEnd().length);
        out += core ? `${lead}$${core}$${trail}` : run;
      } else {
        out += run;
      }
      i = j;
    } else {
      out += line[i];
      i += 1;
    }
  }
  return out;
}

/**
 * Normalises LLM output so KaTeX can render it:
 * - `\(...\)` → `$...$`, `\[...\]` → `$$...$$`
 * - collapse doubled braces (`{{x}}` → `{x}`)
 * - wrap bare LaTeX expressions (e.g. `\sqrt{x}`) in `$...$`
 */
export function normalizeMath(input: string): string {
  if (!input) return input;
  let s = input;
  // NB: use function replacements — a "$$" replacement string inserts a literal "$".
  s = s.replace(/\\\[/g, () => "$$").replace(/\\\]/g, () => "$$");
  s = s.replace(/\\\(/g, () => "$").replace(/\\\)/g, () => "$");
  return s.split("\n").map(wrapBareInLine).join("\n");
}

interface MarkdownMathProps {
  text: string;
  className?: string;
}

/** Renders Markdown (GFM) with KaTeX math support. */
export default function MarkdownMath({ text, className }: MarkdownMathProps) {
  const normalized = useMemo(() => normalizeMath(text ?? ""), [text]);

  return (
    <div className={cn("markdown-body break-words", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath, remarkBreaks]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, errorColor: "#ef4444" }]]}
        components={{
          a: ({ node: _node, ...props }) => (
            <a
              {...props}
              target="_blank"
              rel="noreferrer"
              className="text-primary-400 underline underline-offset-2"
            />
          ),
          table: ({ node: _node, ...props }) => (
            <div className="overflow-x-auto">
              <table {...props} />
            </div>
          ),
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
