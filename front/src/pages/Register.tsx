import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authAPI, getErrorMessage } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { GitBranch, Eye, EyeOff } from 'lucide-react';
import type { RegisterPayload } from '../types/domain';

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState<RegisterPayload>({ name: '', email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.password) {
      toast.error('Please fill in all fields');
      return;
    }
    if (form.password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    setLoading(true);
    try {
      await authAPI.register(form);
      toast.success('Account created! Please sign in.');
      navigate('/login');
    } catch (err) {
      toast.error(getErrorMessage(err, 'Registration failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#0d0f12' }}>
      <div className="w-full max-w-sm px-4">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-10">
          <GitBranch className="w-5 h-5 text-green-accent" />
          <span className="font-mono text-lg font-semibold text-text-primary">
            merge<span className="text-green-accent">intel</span>
          </span>
        </div>

        <div className="bg-surface border border-border-subtle rounded-lg p-7">
          <h1 className="text-xl font-semibold text-text-primary mb-1">Create account</h1>
          <p className="text-sm text-text-muted mb-6">Start analyzing pull requests with AI</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name" className="text-text-secondary text-xs">Full name</Label>
              <Input
                id="name"
                name="name"
                type="text"
                value={form.name}
                onChange={handleChange}
                placeholder="Jane Smith"
                className="bg-background border-border-subtle text-text-primary placeholder:text-text-muted font-mono text-sm h-9 focus:ring-1 focus:ring-green-accent/50 focus:border-green-accent/50"
                autoComplete="name"
              />
            </div>

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
                  placeholder="Min. 8 characters"
                  className="bg-background border-border-subtle text-text-primary placeholder:text-text-muted font-mono text-sm h-9 pr-9 focus:ring-1 focus:ring-green-accent/50 focus:border-green-accent/50"
                  autoComplete="new-password"
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
              {loading ? 'Creating account...' : 'Create account'}
            </Button>
          </form>
        </div>

        <p className="text-center text-sm text-text-muted mt-5">
          Already have an account?{' '}
          <Link to="/login" className="text-green-accent hover:text-green-accent/80 transition-colors duration-150">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
