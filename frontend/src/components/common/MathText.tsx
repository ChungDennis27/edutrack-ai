import { Fragment, useMemo } from "react";
import { BlockMath, InlineMath } from "react-katex";
import { cn } from "@/lib/utils";

type Segment = { type: "text" | "inline" | "block"; value: string };

/** Delimiters the LLM may emit, in priority order (longest/block first). */
const DELIMITERS: { open: string; close: string; type: "inline" | "block" }[] = [
  { open: "$$", close: "$$", type: "block" },
  { open: "\\[", close: "\\]", type: "block" },
  { open: "\\(", close: "\\)", type: "inline" },
  { open: "$", close: "$", type: "inline" },
];

/**
 * Splits a string into plain-text, inline and display math segments.
 * Supports `$...$`, `$$...$$`, `\(...\)` and `\[...\]`.
 * Unclosed delimiters fall back to literal text.
 */
function tokenize(text: string): Segment[] {
  const segments: Segment[] = [];
  let buffer = "";
  let i = 0;

  const flush = () => {
    if (buffer) {
      segments.push({ type: "text", value: buffer });
      buffer = "";
    }
  };

  while (i < text.length) {
    const delimiter = DELIMITERS.find((d) => text.startsWith(d.open, i));

    if (delimiter) {
      const end = text.indexOf(delimiter.close, i + delimiter.open.length);
      if (end !== -1) {
        flush();
        segments.push({
          type: delimiter.type,
          value: text.slice(i + delimiter.open.length, end),
        });
        i = end + delimiter.close.length;
        continue;
      }
    }

    buffer += text[i];
    i += 1;
  }

  flush();
  return segments;
}

interface MathTextProps {
  text: string;
  className?: string;
}

/** Renders a string with KaTeX maths support, preserving newlines. */
export default function MathText({ text, className }: MathTextProps) {
  const segments = useMemo(() => tokenize(text ?? ""), [text]);
  const hasBlockMath = segments.some((s) => s.type === "block");
  const Wrapper = hasBlockMath ? "div" : "span";

  const renderError = (error: Error) => (
    <span className="text-accent-red" title={error.message}>
      {error.message}
    </span>
  );

  return (
    <Wrapper className={cn("whitespace-pre-wrap break-words", className)}>
      {segments.map((segment, index) => {
        if (segment.type === "block") {
          return (
            <BlockMath key={index} math={segment.value} renderError={renderError} />
          );
        }
        if (segment.type === "inline") {
          return (
            <InlineMath key={index} math={segment.value} renderError={renderError} />
          );
        }
        return <Fragment key={index}>{segment.value}</Fragment>;
      })}
    </Wrapper>
  );
}
