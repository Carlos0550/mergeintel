export interface ApiEnvelope<T> {
  success?: boolean;
  message?: string;
  result?: T;
  data?: T;
  detail?: string;
  err?: string;
  err_code?: string;
  status_code?: number;
}

export interface OAuthAccount {
  provider: string;
  provider_login?: string | null;
  github_login?: string | null;
}

export interface User {
  id: number | string;
  name?: string | null;
  email?: string | null;
  role?: string | null;
  status?: string | null;
  created_at?: string | null;
  oauth_accounts?: OAuthAccount[];
  github_account?: OAuthAccount | null;
  github_login?: string | null;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  setAuth: (_token: string | null, user: User | null) => void;
  setUser: (user: User | null) => void;
  clearAuth: () => void;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  name: string;
}

export interface GitHubStartParams {
  mode: "create" | "link" | "login";
  user_id?: number | string;
}

export interface GitHubCallbackParams {
  code: string;
  state?: string | null;
}

export interface GitHubAuthorization {
  authorization_url?: string;
  user?: User;
}

export interface ParseGitHubPRResult {
  repo_full_name: string;
  pr_number: number;
}

export interface AnalysisAuthor {
  name?: string | null;
  email?: string | null;
  github_login?: string | null;
  additions?: number | null;
  deletions?: number | null;
  commit_count?: number | null;
  inferred_scope?: string | string[] | null;
  scope_confidence?: number | null;
}

export interface ChangedFile {
  path: string;
  change_type?: string | null;
  additions?: number | null;
  deletions?: number | null;
  is_schema_change?: boolean | null;
}

export interface ChecklistItem {
  id?: string | number;
  title: string;
  severity?: "low" | "medium" | "high" | string;
  details?: string | null;
  completed?: boolean;
}

export interface SummaryPayload {
  risk_reasons?: string[];
}

export interface PRAnalysisSummary {
  id: number | string;
  repo_full_name: string;
  pr_number: number;
  pr_title?: string | null;
  risk_score?: number | null;
  status?: "pending" | "processing" | "done" | "error" | string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PRAnalysisDetail extends PRAnalysisSummary {
  base_branch?: string | null;
  head_branch?: string | null;
  commit_count?: number | null;
  additions?: number | null;
  deletions?: number | null;
  summary_text?: string | null;
  divergence_days?: number | null;
  authors?: AnalysisAuthor[];
  files?: ChangedFile[];
  checklist?: ChecklistItem[];
  risk_reasons?: string[];
  summary_payload?: SummaryPayload | null;
  merge_divergence_days?: number | null;
}

export interface ChatMessage {
  id?: number | string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  created_at?: string | null;
}

export interface ChatHistoryResult {
  messages?: ChatMessage[];
  history?: ChatMessage[];
}

export interface ChatStreamChunk {
  content: string;
}

export interface ChatStreamDone {
  session_id: string;
  analysis_id: string;
  message: ChatMessage;
}
