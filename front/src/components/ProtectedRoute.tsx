import React from 'react';
import { Navigate } from 'react-router-dom';
import { authAPI, extractResult } from '../lib/api';
import { useAuthStore } from '../store/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isAuthenticated, setUser, clearAuth } = useAuthStore();
  const [isCheckingSession, setIsCheckingSession] = React.useState(!isAuthenticated);

  React.useEffect(() => {
    if (isAuthenticated) {
      setIsCheckingSession(false);
      return;
    }

    let isMounted = true;

    const syncSession = async () => {
      try {
        const res = await authAPI.me();
        const user = extractResult(res);
        if (!isMounted) return;
        setUser(user);
      } catch {
        if (!isMounted) return;
        clearAuth();
      } finally {
        if (isMounted) {
          setIsCheckingSession(false);
        }
      }
    };

    void syncSession();

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, setUser, clearAuth]);

  if (isCheckingSession) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#0d0f12' }}>
        <p className="font-mono text-sm text-text-muted">Checking session...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
};
