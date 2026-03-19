import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { authAPI } from '../lib/api';
import type { User as AppUser } from '../types/domain';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { GitBranch, LogOut, User, ChevronRight } from 'lucide-react';

interface Breadcrumb {
  label: string;
  to: string;
}

const getInitials = (name?: string | null, email?: string | null) => {
  if (name) {
    return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);
  }
  if (email) return email[0].toUpperCase();
  return 'U';
};

const getBreadcrumb = (pathname: string): Breadcrumb[] => {
  if (pathname === '/dashboard') return [{ label: 'Dashboard', to: '/dashboard' }];
  if (pathname === '/profile') return [{ label: 'Profile', to: '/profile' }];
  if (pathname.includes('/chat')) {
    const id = pathname.split('/')[2];
    return [
      { label: 'Dashboard', to: '/dashboard' },
      { label: 'Analysis', to: `/analysis/${id}` },
      { label: 'Chat', to: pathname },
    ];
  }
  if (pathname.startsWith('/analysis/')) {
    return [
      { label: 'Dashboard', to: '/dashboard' },
      { label: 'Analysis', to: pathname },
    ];
  }
  return [];
};

export const Navbar = () => {
  const { user, clearAuth } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [loggingOut, setLoggingOut] = useState(false);

  const breadcrumbs = getBreadcrumb(location.pathname);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await authAPI.logout();
    } catch {}
    clearAuth();
    navigate('/login');
    setLoggingOut(false);
  };

  const typedUser: AppUser | null = user;

  return (
    <nav className="h-12 border-b border-border-subtle bg-surface flex items-center justify-between px-6 sticky top-0 z-50">
      {/* Logo */}
      <Link to="/dashboard" className="flex items-center gap-2.5">
        <div className="flex items-center gap-1.5">
          <GitBranch className="w-4 h-4 text-green-accent" />
          <span className="font-mono text-sm font-semibold text-text-primary">
            merge<span className="text-green-accent">intel</span>
          </span>
        </div>
      </Link>

      {/* Breadcrumb */}
      {breadcrumbs.length > 0 && (
        <nav className="hidden md:flex items-center gap-1.5 text-xs text-text-muted">
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={crumb.to}>
              {idx > 0 && <ChevronRight className="w-3 h-3" />}
              {idx === breadcrumbs.length - 1 ? (
                <span className="text-text-secondary">{crumb.label}</span>
              ) : (
                <Link to={crumb.to} className="hover:text-text-primary transition-colors duration-150">
                  {crumb.label}
                </Link>
              )}
            </React.Fragment>
          ))}
        </nav>
      )}

      {/* User Menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="w-8 h-8 rounded-full bg-green-accent/15 border border-green-accent/30 flex items-center justify-center text-green-accent font-mono text-xs font-semibold hover:bg-green-accent/20 transition-colors duration-150 outline-none">
            {getInitials(typedUser?.name, typedUser?.email)}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="w-48 bg-surface border-border-subtle"
        >
          <div className="px-3 py-2 border-b border-border-subtle">
            <p className="text-xs text-text-primary font-medium truncate">{typedUser?.name || 'User'}</p>
            <p className="text-xs text-text-muted font-mono truncate">{typedUser?.email}</p>
          </div>
          <DropdownMenuItem asChild>
            <Link to="/profile" className="flex items-center gap-2 cursor-pointer text-text-secondary hover:text-text-primary">
              <User className="w-3.5 h-3.5" />
              Profile
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator className="bg-border-subtle" />
          <DropdownMenuItem
            onClick={handleLogout}
            disabled={loggingOut}
            className="flex items-center gap-2 cursor-pointer text-red-accent hover:text-red-accent focus:text-red-accent"
          >
            <LogOut className="w-3.5 h-3.5" />
            {loggingOut ? 'Signing out...' : 'Sign out'}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </nav>
  );
};
