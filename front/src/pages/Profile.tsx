import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { authAPI, extractResult } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import { Navbar } from '../components/Navbar';
import { toast } from 'sonner';
import {
  User,
  Mail,
  Shield,
  Github,
  Lock,
  CheckCircle,
  XCircle,
  Calendar,
} from 'lucide-react';
import type { GitHubStartParams, OAuthAccount, User as UserType } from '../types/domain';

const formatDate = (iso?: string | null) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  });
};

export default function Profile() {
  const { user: storedUser, setUser } = useAuthStore();
  const [githubLinking, setGithubLinking] = useState(false);

  const { data: user } = useQuery<UserType>({
    queryKey: ['me'],
    queryFn: async (): Promise<UserType> => {
      const res = await authAPI.me();
      // Backend returns { success, message, result: { id, name, email, role, status } }
      const u = extractResult(res);
      setUser(u);
      return u;
    },
    initialData: storedUser ?? undefined,
  });

  const handleLinkGitHub = async () => {
    setGithubLinking(true);
    try {
      const params: GitHubStartParams = { mode: 'link' };
      if (user?.id) params.user_id = user.id;
      const res = await authAPI.githubStart(params);
      // Backend returns { success, message, result: { authorization_url, ... } }
      const authUrl = extractResult(res)?.authorization_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        toast.error('Failed to start GitHub linking');
        setGithubLinking(false);
      }
    } catch {
      toast.error('Failed to link GitHub account');
      setGithubLinking(false);
    }
  };

  const githubAccount: OAuthAccount | { provider_login?: string | null } | null =
    user?.oauth_accounts?.find((a) => a.provider === 'github') ||
    user?.github_account ||
    (user?.github_login ? { provider_login: user.github_login } : null);

  const githubHandle = githubAccount
    ? ('github_login' in githubAccount ? githubAccount.github_login : githubAccount.provider_login)
    : null;

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#0d0f12' }}>
      <Navbar />
      <main className="max-w-2xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-text-primary mb-1">Profile</h1>
          <p className="text-sm text-text-muted">Manage your account and integrations</p>
        </div>

        {/* User Info */}
        <div className="bg-surface border border-border-subtle rounded-lg p-6 mb-4">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-14 h-14 rounded-full bg-green-accent/15 border border-green-accent/30 flex items-center justify-center text-green-accent font-mono text-lg font-semibold">
              {(user?.name || user?.email || 'U').split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)}
            </div>
            <div>
              <h2 className="text-text-primary font-semibold">{user?.name || 'Unknown'}</h2>
              <p className="font-mono text-sm text-text-muted">{user?.email}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-3 bg-background rounded border border-border-subtle">
              <div className="flex items-center gap-2 mb-1">
                <User className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs text-text-muted">Full Name</span>
              </div>
              <p className="text-sm text-text-primary">{user?.name || '—'}</p>
            </div>

            <div className="p-3 bg-background rounded border border-border-subtle">
              <div className="flex items-center gap-2 mb-1">
                <Mail className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs text-text-muted">Email</span>
              </div>
              <p className="font-mono text-sm text-text-primary">{user?.email || '—'}</p>
            </div>

            <div className="p-3 bg-background rounded border border-border-subtle">
              <div className="flex items-center gap-2 mb-1">
                <Shield className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs text-text-muted">Role</span>
              </div>
              <span className="font-mono text-xs px-2 py-0.5 bg-blue-accent/10 border border-blue-accent/30 rounded text-blue-accent">
                {user?.role || 'user'}
              </span>
            </div>

            <div className="p-3 bg-background rounded border border-border-subtle">
              <div className="flex items-center gap-2 mb-1">
                {user?.status === 'active'
                  ? <CheckCircle className="w-3.5 h-3.5 text-green-accent" />
                  : <XCircle className="w-3.5 h-3.5 text-text-muted" />}
                <span className="text-xs text-text-muted">Status</span>
              </div>
              <span className={`font-mono text-xs px-2 py-0.5 rounded border ${
                user?.status === 'active'
                  ? 'bg-green-accent/10 border-green-accent/30 text-green-accent'
                  : 'bg-surface border-border-subtle text-text-muted'
              }`}>
                {user?.status || 'active'}
              </span>
            </div>

            {user?.created_at && (
              <div className="p-3 bg-background rounded border border-border-subtle">
                <div className="flex items-center gap-2 mb-1">
                  <Calendar className="w-3.5 h-3.5 text-text-muted" />
                  <span className="text-xs text-text-muted">Member since</span>
                </div>
                <p className="font-mono text-xs text-text-secondary">{formatDate(user.created_at)}</p>
              </div>
            )}
          </div>
        </div>

        {/* GitHub Account */}
        <div className="bg-surface border border-border-subtle rounded-lg p-6 mb-4">
          <h3 className="text-sm font-semibold text-text-secondary mb-4 flex items-center gap-2">
            <Github className="w-4 h-4" />
            GitHub Account
          </h3>

          {githubAccount ? (
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-border-subtle flex items-center justify-center">
                <Github className="w-4 h-4 text-text-secondary" />
              </div>
              <div>
                <p className="text-text-primary text-sm font-medium">@{githubHandle}</p>
                <p className="text-xs text-green-accent">Connected</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-text-secondary text-sm">No GitHub account linked</p>
                <p className="text-text-muted text-xs mt-0.5">Link your GitHub account to analyze private repositories</p>
              </div>
              <button
                onClick={handleLinkGitHub}
                disabled={githubLinking}
                className="flex items-center gap-2 px-4 py-2 rounded border border-border-subtle bg-surface-elevated hover:bg-[#1e2128] text-text-secondary hover:text-text-primary text-sm transition-colors duration-150 disabled:opacity-50"
              >
                <Github className="w-4 h-4" />
                {githubLinking ? 'Redirecting...' : 'Link GitHub'}
              </button>
            </div>
          )}
        </div>

        {/* Password (disabled) */}
        <div className="bg-surface border border-border-subtle rounded-lg p-6 opacity-60">
          <h3 className="text-sm font-semibold text-text-secondary mb-4 flex items-center gap-2">
            <Lock className="w-4 h-4" />
            Password
          </h3>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-text-secondary text-sm">Change your password</p>
              <p className="text-text-muted text-xs mt-0.5">Coming soon</p>
            </div>
            <button
              disabled
              className="px-4 py-2 rounded border border-border-subtle bg-surface text-text-muted text-sm cursor-not-allowed"
            >
              Change password
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
