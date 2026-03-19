import axios, { AxiosError, type AxiosResponse } from 'axios';
import { useAuthStore } from '../store/authStore';
import type {
  ApiEnvelope,
  ChatHistoryResult,
  ChatMessage,
  ChatStreamChunk,
  ChatStreamDone,
  GitHubAuthorization,
  GitHubCallbackParams,
  GitHubStartParams,
  LoginPayload,
  ParseGitHubPRResult,
  PRAnalysisDetail,
  PRAnalysisSummary,
  RegisterPayload,
  User,
} from '../types/domain';

const BACKEND_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.REACT_APP_API_BASE_URL ||
  'http://localhost:8000';
const needsNgrokBypass = BACKEND_URL.includes('ngrok');

export const api = axios.create({
  baseURL: BACKEND_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    ...(needsNgrokBypass
      ? {
          // Required to bypass ngrok browser warning page on the free tier.
          'ngrok-skip-browser-warning': 'true',
        }
      : {}),
  },
});

// Response interceptor: handle 401
const PUBLIC_PATHS = ['/login', '/register', '/auth/callback'];
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiEnvelope<unknown>>) => {
    if (error.response?.status === 401) {
      const isPublicPath = PUBLIC_PATHS.some((p) =>
        window.location.pathname.startsWith(p)
      );
      useAuthStore.getState().clearAuth();
      if (!isPublicPath) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Helper: extract result from API response
// Backend returns: { success, message, result: ... }
export const extractResult = <T>(res: AxiosResponse<ApiEnvelope<T> | T>): T => {
  const data = res.data as ApiEnvelope<T>;
  return (data.result ?? data.data ?? res.data) as T;
};

export const getErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError<ApiEnvelope<unknown>>(error)) {
    const detail = error.response?.data?.detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string') {
            return item.msg;
          }
          return null;
        })
        .filter((message): message is string => Boolean(message));

      if (messages.length > 0) {
        return messages.join('. ');
      }
    }

    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }

    return (
      error.response?.data?.message ||
      error.response?.data?.err ||
      fallback
    );
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
};

type ChatStreamEvent =
  | { event: 'chunk'; data: ChatStreamChunk }
  | { event: 'done'; data: ChatStreamDone }
  | { event: 'error'; data: { message?: string; detail?: string } }
  | { event: string; data: unknown };

const parseChatSseEvent = (rawEvent: string): ChatStreamEvent | null => {
  const lines = rawEvent
    .split('\n')
    .map((line) => line.trimEnd())
    .filter(Boolean);
  if (lines.length === 0) return null;

  let event = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
      continue;
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) return null;

  try {
    return { event, data: JSON.parse(dataLines.join('\n')) } as ChatStreamEvent;
  } catch {
    return null;
  }
};

const readErrorResponse = async (response: Response, fallback: string): Promise<string> => {
  const contentType = response.headers.get('content-type') || '';
  try {
    if (contentType.includes('application/json')) {
      const data = (await response.json()) as ApiEnvelope<unknown>;
      return (
        (typeof data.detail === 'string' && data.detail) ||
        data.message ||
        data.err ||
        fallback
      );
    }

    const text = await response.text();
    return text.trim() || fallback;
  } catch {
    return fallback;
  }
};

interface StreamChatOptions {
  signal?: AbortSignal;
  onChunk: (chunk: string) => void;
}

// Auth endpoints
export const authAPI = {
  register: (data: RegisterPayload) => api.post<ApiEnvelope<User>>('/auth/user/new', data),
  login: (data: LoginPayload) => api.post<ApiEnvelope<User>>('/auth/login', data),
  me: () => api.get<ApiEnvelope<User>>('/auth/me'),
  logout: () => api.post('/auth/logout'),
  githubStart: (params: GitHubStartParams) =>
    api.get<ApiEnvelope<GitHubAuthorization>>('/auth/github/start', { params }),
  githubCallback: (params: GitHubCallbackParams) =>
    api.get<ApiEnvelope<GitHubAuthorization | User>>('/auth/github/callback', { params }),
};

// PR analysis endpoints
export const prAPI = {
  analyze: (data: { pr_url: string }) =>
    api.post<ApiEnvelope<PRAnalysisSummary>>('/pr/analyze', data),
  history: () => api.get<ApiEnvelope<PRAnalysisSummary[]>>('/pr/history'),
  getAnalysis: (id: number | string) => api.get<ApiEnvelope<PRAnalysisDetail>>(`/pr/${id}`),
  getChecklist: (id: number | string) =>
    api.get<ApiEnvelope<PRAnalysisDetail['checklist']>>(`/pr/${id}/checklist`),
  deleteAnalysis: (id: number | string) => api.delete(`/pr/${id}`),
};

// Chat endpoints
export const chatAPI = {
  sendMessage: (analysisId: number | string, content: string) =>
    api.post<ApiEnvelope<ChatMessage | { message?: ChatMessage | string; reply?: ChatMessage | string }>>(
      `/chat/${analysisId}/message`,
      { message: content }
    ),
  streamMessage: async (
    analysisId: number | string,
    content: string,
    { signal, onChunk }: StreamChatOptions
  ): Promise<ChatStreamDone> => {
    const response = await fetch(`${BACKEND_URL}/chat/${analysisId}/stream`, {
      method: 'POST',
      credentials: 'include',
      signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(needsNgrokBypass ? { 'ngrok-skip-browser-warning': 'true' } : {}),
      },
      body: JSON.stringify({ message: content }),
    });

    if (!response.ok || !response.body) {
      throw new Error(await readErrorResponse(response, 'Failed to send message'));
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let donePayload: ChatStreamDone | null = null;

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

      let boundaryIndex = buffer.indexOf('\n\n');
      while (boundaryIndex !== -1) {
        const rawEvent = buffer.slice(0, boundaryIndex);
        buffer = buffer.slice(boundaryIndex + 2);

        const event = parseChatSseEvent(rawEvent);
        if (event?.event === 'chunk' && event.data && typeof event.data === 'object' && 'content' in event.data) {
          onChunk(String(event.data.content ?? ''));
        }

        if (event?.event === 'done') {
          donePayload = event.data as ChatStreamDone;
        }

        if (event?.event === 'error') {
          const message =
            event.data && typeof event.data === 'object'
              ? String(
                  ('message' in event.data && event.data.message) ||
                    ('detail' in event.data && event.data.detail) ||
                    'Failed to send message'
                )
              : 'Failed to send message';
          throw new Error(message);
        }

        boundaryIndex = buffer.indexOf('\n\n');
      }

      if (done) {
        break;
      }
    }

    if (!donePayload) {
      throw new Error('The chat stream ended before returning a final message.');
    }

    return donePayload;
  },
  getHistory: (analysisId: number | string) =>
    api.get<ApiEnvelope<ChatHistoryResult | ChatMessage[]>>(`/chat/${analysisId}/history`),
  clearHistory: (analysisId: number | string) => api.delete(`/chat/${analysisId}`),
};

// Parse GitHub PR URL -> { repo_full_name, pr_number }
export const parseGitHubPRUrl = (url: string): ParseGitHubPRResult | null => {
  const match = url.match(/github\.com\/([^/]+\/[^/]+)\/pull\/(\d+)/);
  if (!match) return null;
  return {
    repo_full_name: match[1],
    pr_number: parseInt(match[2], 10),
  };
};
