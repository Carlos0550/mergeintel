import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authAPI, extractResult, getErrorMessage } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import { toast } from 'sonner';
import { GitBranch } from 'lucide-react';
import type { User } from '../types/domain';

const isUser = (value: User | { user?: User }): value is User => 'id' in value;

export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth } = useAuthStore();

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const error = searchParams.get('error');

      if (error) {
        toast.error('GitHub OAuth failed: ' + error);
        navigate('/login');
        return;
      }

      if (!code) {
        toast.error('Invalid OAuth callback');
        navigate('/login');
        return;
      }

      try {
        // The backend callback sets the session cookie and may return user data
        const res = await authAPI.githubCallback({ code, state });
        const result = extractResult<User | { user?: User }>(res);
        const user = isUser(result) ? result : result.user;

        if (user && user.id) {
          setAuth(null, user);
          toast.success('Signed in with GitHub!');
          navigate('/dashboard');
        } else {
          // Cookie was set — try /auth/me to confirm
          try {
            const meRes = await authAPI.me();
            const u = extractResult(meRes);
            setAuth(null, u);
            toast.success('Signed in with GitHub!');
            navigate('/dashboard');
          } catch {
            toast.error('Authentication failed');
            navigate('/login');
          }
        }
      } catch (err) {
        toast.error(getErrorMessage(err, 'GitHub authentication failed'));
        navigate('/login');
      }
    };

    handleCallback();
  }, [navigate, searchParams, setAuth]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4" style={{ backgroundColor: '#0d0f12' }}>
      <GitBranch className="w-8 h-8 text-green-accent" />
      <p className="font-mono text-text-secondary text-sm">Completing GitHub authentication...</p>
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-green-accent pulse-dot"
            style={{ animationDelay: `${i * 0.2}s` }}
          />
        ))}
      </div>
    </div>
  );
}
