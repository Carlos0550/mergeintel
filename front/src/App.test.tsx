import { cleanup, render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import App from './App';

const { mockMe } = vi.hoisted(() => ({
  mockMe: vi.fn(),
}));

vi.mock('./lib/api', async () => {
  const actual = await vi.importActual<typeof import('./lib/api')>('./lib/api');
  return {
    ...actual,
    authAPI: {
      ...actual.authAPI,
      me: mockMe,
    },
  };
});

describe('App routing smoke tests', () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockMe.mockRejectedValue(new Error('unauthenticated'));
  });

  afterEach(() => {
    cleanup();
    window.history.pushState({}, '', '/');
  });

  it('redirects guests to login from the protected root route', async () => {
    window.history.pushState({}, '', '/');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('renders the register page on /register', async () => {
    window.history.pushState({}, '', '/register');

    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Create account' })).toBeInTheDocument();
  });
});
