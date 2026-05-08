import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/format';

/**
 * Themed markdown renderer used for the Groq investigation memos.
 * Section headings (## Risk Summary, ## What We Observed, ## Why It
 * Matters, ## Recommended Next Step) get a uniform terminal-style
 * eyebrow treatment; the audit-trail footer (after `---`) renders with
 * a more compact mono look to make the model factors visually distinct
 * from the analyst-facing prose.
 */
export function Markdown({ source, className }: { source: string; className?: string }) {
  return (
    <div className={cn('text-sm text-slate-200 leading-relaxed', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h2: ({ children }) => (
            <h2 className="text-[10px] uppercase tracking-[0.2em] text-amber-300/80 font-mono mt-5 mb-1.5 first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-[10px] uppercase tracking-[0.2em] text-amber-300/80 font-mono mt-5 mb-1.5">
              {children}
            </h3>
          ),
          p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
          strong: ({ children }) => <strong className="text-slate-50 font-semibold">{children}</strong>,
          em: ({ children }) => <em className="text-slate-300 italic">{children}</em>,
          code: ({ children }) => (
            <code className="font-mono text-amber-200 bg-amber-900/15 border border-amber-900/30 rounded px-1 py-0.5 text-[0.95em]">
              {children}
            </code>
          ),
          ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-3 ml-1">{children}</ol>,
          ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-3 ml-1">{children}</ul>,
          li: ({ children }) => <li className="text-slate-200 leading-relaxed">{children}</li>,
          hr: () => <hr className="my-4 border-line/50" />,
          a: ({ children, href }) => (
            <a href={href} className="text-accent hover:text-accent2 underline underline-offset-2">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-amber-700/60 pl-3 my-3 text-slate-300 italic">
              {children}
            </blockquote>
          ),
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
