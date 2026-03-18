import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import { prAPI, chatAPI, extractResult, getErrorMessage } from '../lib/api';
import { Navbar } from '../components/Navbar';
import { RiskBadge } from '../components/RiskBadge';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import { toast } from 'sonner';
import {
  Send,
  ArrowLeft,
  User,
  GitBranch,
  MessageSquare,
} from 'lucide-react';
import type { ChatHistoryResult, ChatMessage, ChatStreamDone, PRAnalysisDetail } from '../types/domain';

function DiffViewer({ code }: { code: string }) {
  const lines = code.split('\n');
  return (
    <div className="overflow-x-auto rounded border border-border-subtle bg-[#0a0c0f] text-xs font-mono leading-5">
      {/* Header bar */}
      <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-widest text-text-muted font-semibold">diff</span>
      </div>
      <div className="p-3 space-y-0">
        {lines.map((line, i) => {
          let bg = '';
          let color = 'text-text-muted';
          let prefix = '';

          if (line.startsWith('+++') || line.startsWith('---')) {
            bg = '';
            color = 'text-text-muted';
          } else if (line.startsWith('+')) {
            bg = 'bg-green-accent/10';
            color = 'text-green-accent';
            prefix = '+';
          } else if (line.startsWith('-')) {
            bg = 'bg-red-400/10';
            color = 'text-red-400';
            prefix = '-';
          } else if (line.startsWith('@@')) {
            bg = 'bg-blue-accent/10';
            color = 'text-blue-accent';
          }

          return (
            <div
              key={i}
              className={`flex min-w-0 whitespace-pre rounded-sm px-2 ${bg}`}
            >
              <span className={`w-4 flex-shrink-0 select-none ${prefix === '+' ? 'text-green-accent/60' : prefix === '-' ? 'text-red-400/60' : 'text-text-muted/30'}`}>
                {prefix || ' '}
              </span>
              <span className={`${color} break-all whitespace-pre-wrap`}>{line.slice(line.startsWith('+') || line.startsWith('-') ? 1 : 0)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const markdownComponents: Components = {
  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-2 pl-5 last:mb-0">{children}</ol>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-2 pl-5 last:mb-0">{children}</ul>,
  li: ({ children }) => <li>{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-text-primary">{children}</strong>,
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children }) => {
    const language = /language-(\w+)/.exec(className ?? '')?.[1];
    const code = String(children).replace(/\n$/, '');
    // Multi-line fenced code block
    if (className) {
      if (language === 'diff') {
        return <DiffViewer code={code} />;
      }
      return (
        <pre className="mb-3 overflow-x-auto rounded border border-border-subtle bg-[#0a0c0f] p-3 text-xs font-mono text-text-secondary">
          <code>{code}</code>
        </pre>
      );
    }
    // Inline code
    return (
      <code className="rounded bg-background px-1.5 py-0.5 font-mono text-xs text-text-primary">{children}</code>
    );
  },
};

const formatTime = (iso?: string | null) => {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
};

interface MessageBubbleProps {
  message: ChatMessage;
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.role === 'user';
  return (
    <div className={`flex items-start gap-3 message-in ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono font-semibold flex-shrink-0 border ${
          isUser
            ? 'bg-green-accent/15 border-green-accent/30 text-green-accent'
            : 'bg-blue-accent/15 border-blue-accent/30 text-blue-accent'
        }`}
      >
        {isUser ? <User className="w-3.5 h-3.5" /> : <GitBranch className="w-3.5 h-3.5" />}
      </div>

      {/* Content */}
      <div className={`max-w-[75%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">
            {isUser ? 'You' : 'MergeIntel'}
          </span>
          {message.created_at && (
            <span className="font-mono text-xs text-text-muted">{formatTime(message.created_at)}</span>
          )}
        </div>
        <div
          className={`rounded-lg px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap border ${
            isUser
              ? 'bg-green-accent/10 border-green-accent/20 text-text-primary'
              : 'bg-surface border-border-subtle text-text-secondary'
          }`}
        >
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown components={markdownComponents}>{message.content}</ReactMarkdown>
          )}
        </div>
      </div>
    </div>
  );
};

export default function Chat() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);

  // Fetch analysis info
  const { data: analysis } = useQuery<PRAnalysisDetail>({
    queryKey: ['analysis', id],
    queryFn: async () => {
      const res = await prAPI.getAnalysis(id);
      return extractResult(res);
    },
    enabled: !!id,
  });

  // Fetch chat history
  const { isLoading: historyLoading, error: historyError } = useQuery({
    queryKey: ['chat-history', id],
    queryFn: async () => {
      const res = await chatAPI.getHistory(id);
      const result = extractResult<ChatHistoryResult | ChatMessage[]>(res);
      const msgs = Array.isArray(result) ? result : result?.history || result?.messages || [];
      setMessages(msgs);
      return msgs;
    },
    enabled: !!id,
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => () => streamAbortRef.current?.abort(), []);

  const handleSend = async () => {
    const content = input.trim();
    if (!content || isStreaming) return;

    const timestamp = new Date().toISOString();
    const userId = `local-user-${Date.now()}`;
    const assistantId = `stream-assistant-${Date.now()}`;
    const abortController = new AbortController();
    streamAbortRef.current = abortController;

    setMessages((prev) => [
      ...prev,
      { id: userId, role: 'user', content, created_at: timestamp },
      { id: assistantId, role: 'assistant', content: '', created_at: timestamp },
    ]);
    setInput('');
    setIsStreaming(true);

    try {
      const result: ChatStreamDone = await chatAPI.streamMessage(id, content, {
        signal: abortController.signal,
        onChunk: (chunk) => {
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId
                ? { ...message, content: `${message.content}${chunk}` }
                : message
            )
          );
        },
      });

      setMessages((prev) =>
        prev.map((message) => (message.id === assistantId ? result.message : message))
      );
    } catch (err) {
      if (abortController.signal.aborted) {
        return;
      }

      setMessages((prev) => prev.filter((message) => message.id !== assistantId));
      toast.error(getErrorMessage(err, 'Failed to send message'));
    } finally {
      if (streamAbortRef.current === abortController) {
        streamAbortRef.current = null;
      }
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="h-screen flex flex-col" style={{ backgroundColor: '#0d0f12' }}>
      <Navbar />
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT SIDEBAR */}
        <div className="w-64 border-r border-border-subtle bg-surface flex-shrink-0 flex flex-col">
          <div className="p-4 border-b border-border-subtle">
            <button
              onClick={() => navigate(`/analysis/${id}`)}
              className="flex items-center gap-1.5 text-text-muted hover:text-text-secondary text-xs mb-4 transition-colors duration-150"
            >
              <ArrowLeft className="w-3 h-3" />
              Back to analysis
            </button>
            <p className="text-xs text-text-muted uppercase tracking-wider font-semibold mb-2">PR Context</p>
          </div>

          {analysis && (
            <div className="p-4 space-y-4 overflow-y-auto flex-1">
              <div>
                <p className="text-xs text-text-muted mb-1">Repository</p>
                <p className="font-mono text-xs text-text-secondary">{analysis.repo_full_name}</p>
              </div>
              <div>
                <p className="text-xs text-text-muted mb-1">Pull Request</p>
                <p className="font-mono text-xs text-blue-accent">#{analysis.pr_number}</p>
              </div>
              {analysis.pr_title && (
                <div>
                  <p className="text-xs text-text-muted mb-1">Title</p>
                  <p className="text-xs text-text-primary leading-snug">{analysis.pr_title}</p>
                </div>
              )}
              <div>
                <p className="text-xs text-text-muted mb-1">Risk Score</p>
                <RiskBadge score={analysis.risk_score} />
              </div>
              {analysis.authors && (
                <div>
                  <p className="text-xs text-text-muted mb-1">Authors</p>
                  <p className="font-mono text-xs text-text-secondary">{analysis.authors.length}</p>
                </div>
              )}
            </div>
          )}

          <div className="p-4 border-t border-border-subtle">
            <p className="text-xs text-text-muted">
              Ask questions about the PR — risk, authors, files, or approach.
            </p>
          </div>
        </div>

        {/* MAIN CHAT AREA */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Chat header */}
          <div className="h-12 border-b border-border-subtle flex items-center px-5 gap-2">
            <MessageSquare className="w-4 h-4 text-text-muted" />
            <span className="text-sm text-text-secondary">Chat about this PR</span>
            {isStreaming && (
              <span className="flex items-center gap-1.5 ml-auto">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-accent pulse-dot" />
                <span className="text-xs text-text-muted font-mono">Thinking...</span>
              </span>
            )}
          </div>

          {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-5">
            {historyLoading ? (
              <LoadingState rows={3} />
            ) : historyError ? (
              <ErrorState message="Failed to load chat history" />
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-4">
                <div className="w-12 h-12 rounded-full bg-surface border border-border-subtle flex items-center justify-center">
                  <MessageSquare className="w-5 h-5 text-text-muted" />
                </div>
                <div className="text-center">
                  <p className="text-text-secondary text-sm font-medium">Ask about this PR</p>
                  <p className="text-text-muted text-xs mt-1">Questions about risk, authors, files, or changes</p>
                </div>
                <div className="grid grid-cols-1 gap-2 w-full max-w-sm mt-2">
                  {[
                    'What are the main risks in this PR?',
                    'Summarize the schema changes',
                    'Which author made the most changes?',
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => setInput(suggestion)}
                      className="text-left text-xs px-3 py-2 rounded border border-border-subtle bg-surface hover:border-green-accent/30 hover:text-text-primary text-text-muted transition-colors duration-150 font-mono"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <MessageBubble key={msg.id ?? `${msg.role}-${msg.created_at ?? idx}`} message={msg} />
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-border-subtle">
            <div className="flex gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about this PR... (Enter to send)"
                rows={1}
                className="flex-1 bg-surface border border-border-subtle rounded px-3 py-2.5 text-text-primary placeholder:text-text-muted text-sm font-mono resize-none focus:outline-none focus:ring-1 focus:ring-green-accent/50 focus:border-green-accent/50 transition-colors duration-150"
                style={{ maxHeight: '120px', overflowY: 'auto' }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isStreaming}
                className="h-10 w-10 flex items-center justify-center rounded border border-border-subtle bg-surface-elevated hover:bg-green-accent/10 hover:border-green-accent/30 text-text-muted hover:text-green-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 flex-shrink-0 self-end"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-text-muted mt-1.5 font-mono">Shift+Enter for new line</p>
          </div>
        </div>
      </div>
    </div>
  );
}
