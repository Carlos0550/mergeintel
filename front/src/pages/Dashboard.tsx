import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { prAPI, parseGitHubPRUrl, extractResult, getErrorMessage } from '../lib/api';
import { Navbar } from '../components/Navbar';
import { RiskBadge } from '../components/RiskBadge';
import { StatusPill } from '../components/StatusPill';
import { LoadingState, SkeletonCard } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import { toast } from 'sonner';
import {
  GitPullRequest,
  Search,
  ArrowRight,
  Calendar,
  FileCode2,
  Trash2,
  Clock,
} from 'lucide-react';
import type { ParseGitHubPRResult, PRAnalysisSummary } from '../types/domain';

const formatDate = (iso?: string | null) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
};

interface PRCardProps {
  analysis: PRAnalysisSummary;
  onDelete: (id: PRAnalysisSummary['id']) => void;
}

const PRCard = ({ analysis, onDelete }: PRCardProps) => {
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (!window.confirm('Delete this analysis?')) return;
    setDeleting(true);
    try {
      await prAPI.deleteAnalysis(analysis.id);
      onDelete(analysis.id);
      toast.success('Analysis deleted');
    } catch {
      toast.error('Failed to delete analysis');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      onClick={() => navigate(`/analysis/${analysis.id}`)}
      className="group bg-surface border border-border-subtle rounded-lg p-5 cursor-pointer hover:border-green-accent/30 transition-colors duration-150 flex flex-col"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="font-mono text-xs text-text-muted">{analysis.repo_full_name}</span>
            <span className="font-mono text-xs text-blue-accent">#{analysis.pr_number}</span>
          </div>
          <p className="text-text-primary text-sm font-medium leading-snug truncate">
            {analysis.pr_title || 'Untitled PR'}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <RiskBadge score={analysis.risk_score} />
          <StatusPill status={analysis.status} />
        </div>
      </div>

      <div className="flex items-center justify-between mt-4">
        <div className="flex items-center gap-1.5 text-text-muted">
          <Calendar className="w-3 h-3" />
          <span className="font-mono text-xs">{formatDate(analysis.created_at)}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-accent/10 text-text-muted hover:text-red-accent transition-all duration-150 disabled:opacity-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <ArrowRight className="w-3.5 h-3.5 text-text-muted group-hover:text-green-accent group-hover:translate-x-0.5 transition-all duration-150" />
        </div>
      </div>
    </div>
  );
};

export default function Dashboard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [prUrl, setPrUrl] = useState('');
  const [urlError, setUrlError] = useState('');

  const { data, isLoading, error, refetch } = useQuery<PRAnalysisSummary[]>({
    queryKey: ['pr-history'],
    queryFn: async () => {
      const res = await prAPI.history();
      // Backend returns { success, message, result: [...] }
      const result = extractResult(res);
      return Array.isArray(result) ? result : [];
    },
  });

  const analyzeMutation = useMutation<PRAnalysisSummary, Error, ParseGitHubPRResult>({
    mutationFn: async ({ repo_full_name, pr_number }: ParseGitHubPRResult) => {
      const res = await prAPI.analyze({
        pr_url: `https://github.com/${repo_full_name}/pull/${pr_number}`,
      });
      // Backend returns { success, message, result: { id, ... } }
      return extractResult(res);
    },
    onSuccess: (analysis) => {
      toast.success('Analysis started!');
      queryClient.invalidateQueries({ queryKey: ['pr-history'] });
      navigate(`/analysis/${analysis.id}`);
    },
    onError: (err) => {
      toast.error(getErrorMessage(err, 'Failed to start analysis'));
    },
  });

  const handleAnalyze = () => {
    setUrlError('');
    if (!prUrl.trim()) {
      setUrlError('Enter a GitHub PR URL');
      return;
    }
    const parsed = parseGitHubPRUrl(prUrl);
    if (!parsed) {
      setUrlError('Invalid URL. Expected: https://github.com/owner/repo/pull/123');
      return;
    }
    analyzeMutation.mutate(parsed);
  };

  const handleDelete = (id: PRAnalysisSummary['id']) => {
    queryClient.setQueryData<PRAnalysisSummary[] | undefined>(['pr-history'], (old) => {
      if (!old) return old;
      return Array.isArray(old) ? old.filter((a) => a.id !== id) : old;
    });
  };

  const analyses = Array.isArray(data) ? data : [];

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#0d0f12' }}>
      <Navbar />
      <main className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-text-primary mb-1">Dashboard</h1>
          <p className="text-sm text-text-muted">Analyze pull requests and manage your history</p>
        </div>

        {/* PR URL Input */}
        <div className="bg-surface border border-border-subtle rounded-lg p-5 mb-8">
          <label className="block text-xs text-text-secondary mb-2 font-medium">
            Analyze a Pull Request
          </label>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <GitPullRequest className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
              <input
                type="text"
                value={prUrl}
                onChange={(e) => {
                  setPrUrl(e.target.value);
                  setUrlError('');
                }}
                onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
                placeholder="https://github.com/owner/repo/pull/123"
                className="w-full h-10 pl-9 pr-4 bg-background border border-border-subtle rounded text-text-primary font-mono text-sm placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-green-accent/50 focus:border-green-accent/50 transition-colors duration-150"
              />
            </div>
            <button
              onClick={handleAnalyze}
              disabled={analyzeMutation.isPending}
              className="h-10 px-5 bg-green-accent hover:bg-green-accent/90 text-background text-sm font-semibold rounded flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150"
            >
              {analyzeMutation.isPending ? (
                <>
                  <span className="w-1.5 h-1.5 rounded-full bg-background pulse-dot" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Search className="w-3.5 h-3.5" />
                  Analyze PR
                </>
              )}
            </button>
          </div>
          {urlError && (
            <p className="mt-2 text-xs text-red-accent font-mono">{urlError}</p>
          )}
          <p className="mt-2 text-xs text-text-muted font-mono">
            Accepts: https://github.com/{'{'}owner{'}'}/{'{'}repo{'}'}/pull/{'{'}number{'}'}
          </p>
        </div>

        {/* History */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Recent Analyses</h2>
            {analyses.length > 0 && (
              <span className="font-mono text-xs text-text-muted">{analyses.length} total</span>
            )}
          </div>

          {isLoading ? (
            <div className="grid gap-3">
              {[1, 2, 3].map((i) => <SkeletonCard key={i} />)}
            </div>
          ) : error ? (
            <ErrorState message="Failed to load analysis history" onRetry={refetch} />
          ) : analyses.length === 0 ? (
            <div className="text-center py-16 border border-dashed border-border-subtle rounded-lg">
              <Clock className="w-8 h-8 text-text-muted mx-auto mb-3" />
              <p className="text-text-secondary text-sm">No analyses yet</p>
              <p className="text-text-muted text-xs mt-1">Paste a GitHub PR URL above to get started</p>
            </div>
          ) : (
            <div className="grid gap-3">
              {analyses.map((analysis) => (
                <PRCard key={analysis.id} analysis={analysis} onDelete={handleDelete} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
