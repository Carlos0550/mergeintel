import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authAPI, extractResult, getErrorMessage } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { GitBranch, Eye, EyeOff, Github } from 'lucide-react';
import type { LoginPayload } from '../types/domain';

export default function Login() {
  const navigate = useNavigate();
  const { isAuthenticated, setAuth, setUser, clearAuth } = useAuthStore();
  const [form, setForm] = useState<LoginPayload>({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [githubLoading, setGithubLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [checkingSession, setCheckingSession] = useState(!isAuthenticated);

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true });
      return;
    }

    let isMounted = true;

    const syncSession = async () => {
      try {
        const res = await authAPI.me();
        const user = extractResult(res);
        if (!isMounted) return;
        setUser(user);
        navigate('/dashboard', { replace: true });
      } catch {
        if (!isMounted) return;
        clearAuth();
      } finally {
        if (isMounted) {
          setCheckingSession(false);
        }
      }
    };

    void syncSession();

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, navigate, setUser, clearAuth]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form.email || !form.password) {
      toast.error('Please fill in all fields');
      return;
    }
    setLoading(true);
    try {
      const res = await authAPI.login(form);
      // Backend returns { success, message, result: { id, name, email, role, status } }
      // Auth is cookie-based — session cookie is set automatically by the browser
      const user = extractResult(res);
      setAuth(null, user);
      navigate('/dashboard');
    } catch (err) {
      toast.error(getErrorMessage(err, 'Invalid credentials'));
    } finally {
      setLoading(false);
    }
  };

  const handleGitHub = async () => {
    setGithubLoading(true);
    try {
      const res = await authAPI.githubStart({ mode: 'login' });
      // Backend returns { success, message, result: { authorization_url, ... } }
      const authUrl = extractResult(res)?.authorization_url;
      if (authUrl) {
        window.location.href = authUrl;
      } else {
        toast.error('Failed to start GitHub OAuth');
        setGithubLoading(false);
      }
    } catch {
      toast.error('GitHub OAuth failed');
      setGithubLoading(false);
    }
  };

  if (checkingSession) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background" style={{ backgroundColor: '#0d0f12' }}>
        <p className="font-mono text-sm text-text-muted">Checking session...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background" style={{ backgroundColor: '#0d0f12' }}>
      <div className="w-full max-w-sm px-4">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-10">
          <GitBranch className="w-5 h-5 text-green-accent" />
          <span className="font-mono text-lg font-semibold text-text-primary">
            merge<span className="text-green-accent">intel</span>
          </span>
        </div>

        <div className="bg-surface border border-border-subtle rounded-lg p-7">
          <h1 className="text-xl font-semibold text-text-primary mb-1">Sign in</h1>
          <p className="text-sm text-text-muted mb-6">Access your PR analysis dashboard</p>

          {/* GitHub OAuth button */}
          <button
            type="button"
            onClick={handleGitHub}
            disabled={githubLoading}
            className="w-full flex items-center justify-center gap-2.5 h-10 rounded border border-border-subtle bg-surface-elevated hover:bg-[#1e2128] text-text-secondary hover:text-text-primary text-sm font-medium transition-colors duration-150 mb-5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Github className="w-4 h-4" />
            {githubLoading ? 'Redirecting...' : 'Continue with GitHub'}
          </button>

          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-border-subtle" />
            <span className="text-xs text-text-muted font-mono">or</span>
            <div className="flex-1 h-px bg-border-subtle" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-text-secondary text-xs">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={form.email}
                onChange={handleChange}
                placeholder="you@example.com"
                className="bg-background border-border-subtle text-text-primary placeholder:text-text-muted font-mono text-sm h-9 focus:ring-1 focus:ring-green-accent/50 focus:border-green-accent/50"
                autoComplete="email"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-text-secondary text-xs">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={handleChange}
                  placeholder="••••••••"
                  className="bg-background border-border-subtle text-text-primary placeholder:text-text-muted font-mono text-sm h-9 pr-9 focus:ring-1 focus:ring-green-accent/50 focus:border-green-accent/50"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors duration-150"
                >
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-9 bg-green-accent hover:bg-green-accent/90 text-background font-medium text-sm border-0 mt-2"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </Button>
          </form>
        </div>

        <p className="text-center text-sm text-text-muted mt-5">
          Don't have an account?{' '}
          <Link to="/register" className="text-green-accent hover:text-green-accent/80 transition-colors duration-150">
            Create account
          </Link>
        </p>
      </div>
    </div>
  );
}
