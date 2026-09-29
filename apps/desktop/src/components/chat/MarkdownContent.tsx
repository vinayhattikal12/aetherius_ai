import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, Copy, Download, Maximize2, RefreshCw, Image as ImageIcon } from 'lucide-react';

interface MarkdownContentProps {
  content: string;
  onImageClick?: (url: string) => void;
}

export const MarkdownContent: React.FC<MarkdownContentProps> = ({ content, onImageClick }) => {
  return (
    <div className="prose-clean text-sm leading-relaxed text-white space-y-2.5 break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-lg font-bold text-white mt-4 mb-2 pb-1 border-b border-[#2a2928] first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-bold text-white mt-3.5 mb-1.5 first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-semibold text-white mt-3 mb-1 first:mt-0">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="mb-2 leading-relaxed text-zinc-100 last:mb-0">
              {children}
            </p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-white">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="italic text-zinc-200">{children}</em>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 my-2 space-y-1 text-zinc-200">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 my-2 space-y-1 text-zinc-200">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed pl-0.5">{children}</li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-[#016A71] pl-3 py-0.5 my-2 text-[#949494] italic bg-[#171615]/50 rounded-r-[6px]">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-3 rounded-[8px] border border-[#2a2928]">
              <table className="min-w-full divide-y divide-[#2a2928] text-xs">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-[#171615] text-[#949494] font-medium uppercase tracking-wider">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-[#2a2928] bg-black/40">
              {children}
            </tbody>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 text-left text-xs font-semibold text-white">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 text-zinc-200 text-xs">
              {children}
            </td>
          ),
          img: ({ src, alt }: any) => (
            <MarkdownImage src={src || ''} alt={alt || 'Visual Illustration'} onImageClick={onImageClick} />
          ),
          code: ({ node, className, children, ...props }: any) => {
            const match = /language-(\w+)/.exec(className || '');
            const isInline = !match && !String(children).includes('\n');

            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 mx-0.5 rounded-[5px] bg-[#222120] text-[#34888D] text-[12px] font-mono border border-[#2a2928]"
                  {...props}
                >
                  {children}
                </code>
              );
            }

            const codeText = String(children).replace(/\n$/, '');
            return <CodeBlock language={match ? match[1] : ''} code={codeText} />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

interface MarkdownImageProps {
  src: string;
  alt: string;
  onImageClick?: (url: string) => void;
}

const MarkdownImage: React.FC<MarkdownImageProps> = ({ src, alt, onImageClick }) => {
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [hasError, setHasError] = useState<boolean>(false);
  const [retryKey, setRetryKey] = useState<number>(0);

  const handleRetry = () => {
    setHasError(false);
    setIsLoading(true);
    setRetryKey((prev) => prev + 1);
  };

  const imageSrc = retryKey > 0 ? `${src}${src.includes('?') ? '&' : '?'}retry=${retryKey}` : src;

  return (
    <div className="relative my-3 rounded-[12px] overflow-hidden border border-[#2a2928] bg-[#121214] max-w-2xl group shadow-lg">
      {/* Loading Skeleton */}
      {isLoading && !hasError && (
        <div className="w-full h-64 bg-[#171615] flex flex-col items-center justify-center animate-pulse gap-2">
          <ImageIcon className="w-8 h-8 text-[#34888D]/60 animate-bounce" />
          <span className="text-xs text-[#949494] font-medium">Loading visual render...</span>
        </div>
      )}

      {/* Error Fallback Card */}
      {hasError ? (
        <div className="w-full p-6 bg-[#171615] flex flex-col items-center justify-center text-center gap-3">
          <div className="p-3 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400">
            <ImageIcon className="w-6 h-6" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">Visual Image Preview Unavailable</div>
            <div className="text-xs text-[#949494] mt-1 max-w-sm">
              The image could not be loaded directly from the remote endpoint.
            </div>
          </div>
          <button
            onClick={handleRetry}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-[9px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-medium transition-colors shadow-sm"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Loading</span>
          </button>
        </div>
      ) : (
        <div className="relative">
          <img
            key={imageSrc}
            src={imageSrc}
            alt={alt}
            onLoad={() => setIsLoading(false)}
            onError={() => {
              setIsLoading(false);
              setHasError(true);
            }}
            className={`w-full max-h-[500px] object-contain cursor-pointer transition-opacity duration-300 ${
              isLoading ? 'opacity-0 h-0' : 'opacity-100'
            }`}
            onClick={() => onImageClick && onImageClick(src)}
          />

          {/* Hover Controls */}
          {!isLoading && (
            <div className="absolute top-2 right-2 flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
              {onImageClick && (
                <button
                  onClick={() => onImageClick(src)}
                  className="p-1.5 rounded-[8px] bg-black/75 hover:bg-black text-white text-xs backdrop-blur-sm transition-all border border-white/10"
                  title="View Fullscreen"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
              )}
              <a
                href={src}
                download={`${alt.slice(0, 20).replace(/[^a-z0-9]/gi, '_')}.png`}
                target="_blank"
                rel="noreferrer"
                className="p-1.5 rounded-[8px] bg-black/75 hover:bg-black text-white text-xs backdrop-blur-sm transition-all border border-white/10"
                title="Download Image"
              >
                <Download className="w-3.5 h-3.5" />
              </a>
            </div>
          )}
        </div>
      )}

      {/* Caption footer */}
      {alt && !isLoading && !hasError && (
        <div className="px-3 py-1.5 bg-[#171615] border-t border-[#2a2928] text-[11px] text-[#949494] flex items-center justify-between">
          <span className="truncate max-w-[80%] font-medium">{alt}</span>
          <span className="text-[10px] text-[#34888D] font-mono">Aetherius Visual</span>
        </div>
      )}
    </div>
  );
};

interface CodeBlockProps {
  language: string;
  code: string;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative my-3 rounded-[9px] overflow-hidden border border-[#2a2928] bg-[#0c0c0d]">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-[#171615] border-b border-[#2a2928] text-[11px] text-[#949494]">
        <span className="font-mono lowercase">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] hover:text-white transition-colors"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-emerald-400" />
              <span className="text-emerald-400">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-[12px] leading-relaxed font-mono text-[#dcdcdc] bg-transparent">
        <code>{code}</code>
      </pre>
    </div>
  );
};

