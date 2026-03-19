import { create } from 'zustand';
import type { AuthState, User } from '../types/domain';

const USER_KEY = 'mergeintel_user';

const getStoredUser = (): User | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const user = window.localStorage.getItem(USER_KEY);
    return user ? (JSON.parse(user) as User) : null;
  } catch {
    return null;
  }
};

export const useAuthStore = create<AuthState>((set) => ({
  // Auth is cookie-based (mergeintel_session HttpOnly cookie)
  // We only store user info in localStorage for UI state
  user: getStoredUser(),
  isAuthenticated: !!getStoredUser(),

  setAuth: (_token, user) => {
    // Token param is ignored — backend uses HttpOnly cookies
    if (user) {
      window.localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      window.localStorage.removeItem(USER_KEY);
    }
    set({ user, isAuthenticated: !!user });
  },

  setUser: (user) => {
    if (user) {
      window.localStorage.setItem(USER_KEY, JSON.stringify(user));
    } else {
      window.localStorage.removeItem(USER_KEY);
    }
    set({ user, isAuthenticated: !!user });
  },

  clearAuth: () => {
    window.localStorage.removeItem(USER_KEY);
    set({ user: null, isAuthenticated: false });
  },
}));
