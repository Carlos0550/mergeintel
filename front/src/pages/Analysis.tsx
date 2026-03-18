import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import { prAPI, extractResult } from '../lib/api';
import { Navbar } from '../components/Navbar';
import { RiskBadge } from '../components/RiskBadge';
import { StatusPill } from '../components/StatusPill';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import {
  GitMerge,
  GitCommit,
  FileCode2,
  Plus,
  Minus,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  User,
  CheckSquare,
  Square,
  Shield,
  Clock,
  Database,
} from 'lucide-react';
import type { AnalysisAuthor, ChecklistItem, ChangedFile, PRAnalysisDetail } from '../types/domain';

const markdownComponents: Components = {
  p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-2 pl-5 last:mb-0">{children}</ol>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-2 pl-5 last:mb-0">{children}</ul>,
  li: ({ children }) => <li>{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-text-primary">{children}</strong>,
};

const getRiskColor = (score?: number | null) => {
  const s = Number(score);
  if (!score) return '#6b7280';
  if (s <= 3) return '#4ade80';
  if (s <= 6) return '#facc15';
  return '#f87171';
};

const getRiskBarWidth = (score?: number | null) => {
  const s = Number(score);
  if (!s) return '0%';
  return `${(s / 10) * 100}%`;
};

const getDivergenceColor = (days?: number | null) => {
  const d = Number(days);
  if (d === 0) return 'text-green-accent';
  if (d < 14) return 'text-yellow-accent';
  return 'text-red-accent';
};

const SeverityBadge = ({ severity }: { severity?: ChecklistItem['severity'] }) => {
  const configs = {
    low: 'bg-green-accent/10 border-green-accent/30 text-green-accent',
    medium: 'bg-yellow-accent/10 border-yellow-accent/30 text-yellow-accent',
    high: 'bg-red-accent/10 border-red-accent/30 text-red-accent',
  };
  return (
    <span className={`font-mono text-xs px-2 py-0.5 rounded border ${configs[severity as keyof typeof configs] || configs.low}`}>
      {severity}
    </span>
  );
};

const AuthorCard = ({ author }: { author: AnalysisAuthor }) => {
  const totalChanges = (author.additions || 0) + (author.deletions || 0);
  const confidence = typeof author.scope_confidence === 'number'
    ? author.scope_confidence
    : 0;
  const initials = (author.name || author.github_login || '?')
    .split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);

  return (
    <div className="bg-background border border-border-subtle rounded-lg p-4">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-full bg-blue-accent/15 border border-blue-accent/30 flex items-center justify-center text-blue-accent font-mono text-xs font-semibold flex-shrink-0">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-text-primary text-sm font-medium">{author.name || author.github_login}</p>
          {author.email && (
            <p className="font-mono text-xs text-text-muted truncate">{author.email}</p>
          )}
          <div className="flex items-center gap-3 mt-2">
            <span className="flex items-center gap-1 font-mono text-xs">
              <GitCommit className="w-3 h-3 text-text-muted" />
              <span className="text-text-secondary">{author.commit_count || 0} commits</span>
            </span>
            <span className="font-mono text-xs text-green-accent">+{author.additions || 0}</span>
            <span className="font-mono text-xs text-red-accent">−{author.deletions || 0}</span>
          </div>
          {author.inferred_scope && (
            <div className="mt-2.5 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-muted">Scope confidence</span>
                <span className="font-mono text-xs text-yellow-accent">{Math.round(confidence * 100)}%</span>
              </div>
              <div className="h-1 bg-border-subtle rounded-full overflow-hidden">
                <div
                  className="h-full bg-yellow-accent rounded-full risk-bar-fill"
                  style={{ width: `${confidence * 100}%` }}
                />
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {(Array.isArray(author.inferred_scope)
                  ? author.inferred_scope
                  : [author.inferred_scope]
                ).map((tag, i) => (
                  <span key={i} className="font-mono text-xs px-1.5 py-0.5 bg-yellow-accent/10 border border-yellow-accent/20 text-yellow-accent rounded">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const FilesTable = ({ files }: { files: ChangedFile[] }) => {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? files : files.slice(0, 10);

  const changeTypeColor = (type?: string | null) => {
    const map = {
      added: 'text-green-accent',
      removed: 'text-red-accent',
      modified: 'text-blue-accent',
      renamed: 'text-yellow-accent',
    };
    const normalizedType = type?.toLowerCase();
    return (normalizedType ? map[normalizedType as keyof typeof map] : undefined) || 'text-text-muted';
  };

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-subtle">
              <th className="text-left pb-2 text-xs text-text-muted font-medium pr-4">Path</th>
              <th className="text-left pb-2 text-xs text-text-muted font-medium pr-4">Type</th>
              <th className="text-right pb-2 text-xs text-text-muted font-medium pr-4">+</th>
              <th className="text-right pb-2 text-xs text-text-muted font-medium pr-4">−</th>
              <th className="text-center pb-2 text-xs text-text-muted font-medium">Schema</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((file, idx) => (
              <tr key={idx} className="border-b border-border-subtle/50 hover:bg-surface-elevated transition-colors duration-100">
                <td className="py-2 pr-4">
                  <div className="flex items-center gap-1.5">
                    {file.is_schema_change && (
                      <span className="w-1.5 h-1.5 rounded-full bg-yellow-accent flex-shrink-0" />
                    )}
                    <span className="font-mono text-xs text-text-primary truncate max-w-xs">
                      {file.path}
                    </span>
                  </div>
                </td>
                <td className="py-2 pr-4">
                  <span className={`font-mono text-xs ${changeTypeColor(file.change_type)}`}>
                    {file.change_type || '—'}
                  </span>
                </td>
                <td className="py-2 pr-4 text-right font-mono text-xs text-green-accent">
                  +{file.additions || 0}
                </td>
                <td className="py-2 pr-4 text-right font-mono text-xs text-red-accent">
                  −{file.deletions || 0}
                </td>
                <td className="py-2 text-center">
                  {file.is_schema_change ? (
                    <span className="inline-block w-2 h-2 rounded-full bg-yellow-accent" />
                  ) : (
                    <span className="text-text-muted font-mono text-xs">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {files.length > 10 && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-3 flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary font-mono transition-colors duration-150"
        >
          {expanded ? (
            <><ChevronUp className="w-3 h-3" /> Show less</>
          ) : (
            <><ChevronDown className="w-3 h-3" /> Show all {files.length} files</>
          )}
        </button>
      )}
    </div>
  );
};

const ChecklistSection = ({ items }: { items: ChecklistItem[] }) => {
  const [checked, setChecked] = useState<Record<string, boolean>>(() => {
    const map: Record<string, boolean> = {};
    items.forEach((item) => { map[item.id || item.title] = item.completed || false; });
    return map;
  });

  const toggle = (key: string) => {
    setChecked((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="space-y-2">
      {items.map((item, idx) => {
        const key = String(item.id || item.title || idx);
        const isChecked = checked[key];
        return (
          <div
            key={idx}
            onClick={() => toggle(key)}
            className="flex items-start gap-3 p-3 rounded border border-border-subtle hover:bg-surface-elevated cursor-pointer transition-colors duration-150 group"
          >
            <div className="mt-0.5 flex-shrink-0 text-text-muted group-hover:text-text-secondary transition-colors duration-150">
              {isChecked
                ? <CheckSquare className="w-4 h-4 text-green-accent" />
                : <Square className="w-4 h-4" />
              }
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-sm font-medium ${isChecked ? 'line-through text-text-muted' : 'text-text-primary'}`}>
                  {item.title}
                </span>
                <SeverityBadge severity={item.severity} />
              </div>
              {item.details && (
                <p className="text-xs text-text-muted mt-1 leading-relaxed">{item.details}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default function Analysis() {
  const { id = '' } = useParams();
  const navigate = useNavigate();

  const { data: analysis, isLoading, error, refetch } = useQuery<PRAnalysisDetail>({
    queryKey: ['analysis', id],
    queryFn: async () => {
      const res = await prAPI.getAnalysis(id);
      // Backend returns { success, message, result: { ... } }
      return extractResult(res);
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'processing' || status === 'pending') return 3000;
      return false;
    },
    enabled: !!id,
  });

  const { data: checklistData } = useQuery<ChecklistItem[]>({
    queryKey: ['checklist', id],
    queryFn: async () => {
      const res = await prAPI.getChecklist(id);
      const result = extractResult(res);
      return Array.isArray(result) ? result : [];
    },
    enabled: analysis?.status === 'done',
  });

  if (isLoading) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: '#0d0f12' }}>
        <Navbar />
        <div className="max-w-7xl mx-auto px-6 py-8">
          <LoadingState rows={6} />
        </div>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="min-h-screen" style={{ backgroundColor: '#0d0f12' }}>
        <Navbar />
        <div className="max-w-7xl mx-auto px-6 py-8">
          <ErrorState message="Failed to load analysis" onRetry={refetch} />
        </div>
      </div>
    );
  }

  const isProcessing = analysis.status === 'processing' || analysis.status === 'pending';
  const riskScore = analysis.risk_score;
  const authors = analysis.authors || [];
  const files = analysis.files || [];
  const schemaFiles = files.filter((f) => f.is_schema_change);
  const checklist = checklistData || analysis.checklist || [];
  const riskReasons = analysis.risk_reasons || analysis.summary_payload?.risk_reasons || [];

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#0d0f12' }}>
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Title + meta */}
        <div className="mb-6">
          <div className="flex items-start gap-3 flex-wrap mb-3">
            <h1 className="text-xl font-semibold text-text-primary leading-snug flex-1">
              {analysis.pr_title || `PR #${analysis.pr_number}`}
            </h1>
            <div className="flex items-center gap-2">
              <StatusPill status={analysis.status} />
              <RiskBadge score={riskScore} />
            </div>
          </div>

          {/* Meta pills */}
          <div className="flex flex-wrap gap-2">
            <span className="font-mono text-xs px-2.5 py-1 bg-surface border border-border-subtle rounded text-text-secondary">
              {analysis.repo_full_name}
            </span>
            <span className="font-mono text-xs px-2.5 py-1 bg-blue-accent/10 border border-blue-accent/30 rounded text-blue-accent">
              #{analysis.pr_number}
            </span>
            {analysis.base_branch && analysis.head_branch && (
              <span className="font-mono text-xs px-2.5 py-1 bg-surface border border-border-subtle rounded text-text-secondary flex items-center gap-1">
                <span className="text-text-muted">{analysis.base_branch}</span>
                <span className="text-text-muted">←</span>
                <span className="text-blue-accent">{analysis.head_branch}</span>
              </span>
            )}
            {analysis.commit_count != null && (
              <span className="font-mono text-xs px-2.5 py-1 bg-surface border border-border-subtle rounded text-text-secondary flex items-center gap-1">
                <GitCommit className="w-3 h-3" />
                {analysis.commit_count} commits
              </span>
            )}
            {files.length > 0 && (
              <span className="font-mono text-xs px-2.5 py-1 bg-surface border border-border-subtle rounded text-text-secondary flex items-center gap-1">
                <FileCode2 className="w-3 h-3" />
                {files.length} files
              </span>
            )}
            {(analysis.additions != null || analysis.deletions != null) && (
              <span className="font-mono text-xs px-2.5 py-1 bg-surface border border-border-subtle rounded flex items-center gap-1">
                <span className="text-green-accent">+{analysis.additions || 0}</span>
                <span className="text-text-muted">/</span>
                <span className="text-red-accent">−{analysis.deletions || 0}</span>
              </span>
            )}
          </div>
        </div>

        {isProcessing && (
          <div className="mb-6 p-4 bg-blue-accent/10 border border-blue-accent/30 rounded-lg flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-blue-accent pulse-dot" />
            <p className="text-blue-accent text-sm">Analysis in progress... refreshing automatically</p>
          </div>
        )}

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
          {/* LEFT: Main panel */}
          <div className="space-y-6">
            {/* AI Summary */}
            {analysis.summary_text && (
              <section className="bg-surface border border-border-subtle rounded-lg p-5">
                <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4 flex items-center gap-2">
                  <Shield className="w-3.5 h-3.5" />
                  AI Summary
                </h2>
                <div className="text-text-secondary text-sm leading-relaxed">
                  <ReactMarkdown components={markdownComponents}>
                    {analysis.summary_text}
                  </ReactMarkdown>
                </div>
              </section>
            )}

            {/* Authors */}
            {authors.length > 0 && (
              <section className="bg-surface border border-border-subtle rounded-lg p-5">
                <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4 flex items-center gap-2">
                  <User className="w-3.5 h-3.5" />
                  Authors ({authors.length})
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {authors.map((author, idx) => (
                    <AuthorCard key={idx} author={author} />
                  ))}
                </div>
              </section>
            )}

            {/* Files Changed */}
            {files.length > 0 && (
              <section className="bg-surface border border-border-subtle rounded-lg p-5">
                <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4 flex items-center gap-2">
                  <FileCode2 className="w-3.5 h-3.5" />
                  Files Changed ({files.length})
                </h2>
                <FilesTable files={files} />
              </section>
            )}
          </div>

          {/* RIGHT: Sidebar */}
          <div className="space-y-4">
            {/* Risk Score */}
            <div className="bg-surface border border-border-subtle rounded-lg p-5">
              <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4">Risk Score</h3>
              <div className="flex items-baseline gap-1 mb-3">
                <span
                  className="font-mono font-bold leading-none"
                  style={{ fontSize: '48px', color: getRiskColor(riskScore) }}
                >
                  {riskScore ?? '—'}
                </span>
                <span className="font-mono text-lg text-text-muted">/10</span>
              </div>
              <div className="h-1.5 bg-background rounded-full overflow-hidden mb-4">
                <div
                  className="h-full rounded-full risk-bar-fill"
                  style={{
                    width: getRiskBarWidth(riskScore),
                    backgroundColor: getRiskColor(riskScore),
                  }}
                />
              </div>
              {riskReasons.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs text-text-muted mb-2">Risk factors</p>
                  {riskReasons.map((reason, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-text-secondary">
                      <AlertTriangle className="w-3 h-3 text-yellow-accent flex-shrink-0 mt-0.5" />
                      <span>{reason}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Branch Divergence */}
            {analysis.divergence_days != null && (
              <div className="bg-surface border border-border-subtle rounded-lg p-5">
                <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Branch Divergence</h3>
                <div className="flex items-center gap-2">
                  <Clock className={`w-4 h-4 ${getDivergenceColor(analysis.divergence_days)}`} />
                  <span className={`font-mono text-2xl font-bold ${getDivergenceColor(analysis.divergence_days)}`}>
                    {analysis.divergence_days}
                  </span>
                  <span className="text-sm text-text-muted">days behind</span>
                </div>
                <p className="text-xs text-text-muted mt-2">
                  {analysis.divergence_days === 0
                    ? 'Branch is up to date'
                    : analysis.divergence_days < 14
                    ? 'Minor divergence — review recommended'
                    : 'Significant divergence — conflicts likely'}
                </p>
              </div>
            )}

            {/* Schema Changes */}
            {schemaFiles.length > 0 && (
              <div className="bg-surface border border-border-subtle rounded-lg p-5">
                <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-yellow-accent" />
                  Schema Changes ({schemaFiles.length})
                </h3>
                <div className="space-y-1.5">
                  {schemaFiles.map((file, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-yellow-accent flex-shrink-0" />
                      <span className="font-mono text-xs text-text-secondary truncate">{file.path}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Pre-merge Checklist */}
            {checklist.length > 0 && (
              <div className="bg-surface border border-border-subtle rounded-lg p-5">
                <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Pre-merge Checklist</h3>
                <ChecklistSection items={checklist} />
              </div>
            )}

            {/* Chat CTA */}
            <button
              onClick={() => navigate(`/analysis/${id}/chat`)}
              className="w-full h-10 flex items-center justify-center gap-2 bg-surface-elevated border border-border-subtle rounded text-text-secondary hover:text-text-primary hover:border-green-accent/30 text-sm font-medium transition-colors duration-150"
            >
              <MessageSquare className="w-4 h-4" />
              Chat about this PR
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
