import { UserRole } from '../types';

export const AUTH_TOKEN_KEY = 'studySpace_token';
export const AUTH_USER_KEY = 'studySpace_user';
export const AUTH_LAST_ACTIVITY_KEY = 'studySpace_auth_lastActivityAt';
export const AUTH_REFRESH_EXPIRES_KEY = 'studySpace_auth_refreshExpiresAt';
export const AUTH_EVENT_KEY = 'studySpace_auth_event';
export const AUTH_PENDING_REDIRECT_KEY = 'studySpace_auth_pendingRedirect';

export const ACCESS_TOKEN_REFRESH_SKEW_MS = 60_000;
export const INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000;
export const INACTIVITY_WARNING_MS = 2 * 60 * 1000;

export type AuthEventType = 'login' | 'logout' | 'activity' | 'session-refreshed';

export interface AuthEventPayload {
  type: AuthEventType;
  reason?: string;
  redirectTo?: string;
  at: number;
}

interface JwtPayload {
  exp?: number;
  sub?: string;
}

const now = () => Date.now();

const safeJsonParse = <T,>(raw: string | null): T | null => {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
};

export const tokenResponseToUser = (data: any) => ({
  id: data.user_id,
  name: data.name,
  email: data.email,
  role: data.role as UserRole,
  avatarUrl: data.avatar_url,
  phone: data.phone,
  has_active_waitlist: data.has_active_waitlist,
});

export const getStoredUser = () => safeJsonParse<any>(localStorage.getItem(AUTH_USER_KEY));

export const getAccessToken = () => localStorage.getItem(AUTH_TOKEN_KEY);

export const decodeJwtPayload = (token: string | null): JwtPayload | null => {
  if (!token) return null;
  const [, payload] = token.split('.');
  if (!payload) return null;

  try {
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + (4 - normalized.length % 4) % 4, '=');
    return JSON.parse(window.atob(padded)) as JwtPayload;
  } catch {
    return null;
  }
};

export const getAccessTokenExpiresAt = (token = getAccessToken()): number | null => {
  const exp = decodeJwtPayload(token)?.exp;
  return typeof exp === 'number' ? exp * 1000 : null;
};

export const isAccessTokenExpired = (token = getAccessToken(), skewMs = 0): boolean => {
  const expiresAt = getAccessTokenExpiresAt(token);
  return !expiresAt || expiresAt <= now() + skewMs;
};

export const shouldRefreshAccessToken = (token = getAccessToken()): boolean =>
  Boolean(token) && isAccessTokenExpired(token, ACCESS_TOKEN_REFRESH_SKEW_MS);

export const getLastActivityAt = (): number => {
  const parsed = Number(localStorage.getItem(AUTH_LAST_ACTIVITY_KEY));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : now();
};

export const getRefreshExpiresAt = (): number | null => {
  const raw = localStorage.getItem(AUTH_REFRESH_EXPIRES_KEY);
  if (!raw) return null;
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : null;
};

export const isRefreshSessionExpired = (): boolean => {
  const expiresAt = getRefreshExpiresAt();
  return Boolean(expiresAt && expiresAt <= now());
};

export const isInactive = (): boolean =>
  now() - getLastActivityAt() >= INACTIVITY_TIMEOUT_MS;

export const shouldShowInactivityWarning = (): boolean => {
  const idleMs = now() - getLastActivityAt();
  return idleMs >= INACTIVITY_TIMEOUT_MS - INACTIVITY_WARNING_MS && idleMs < INACTIVITY_TIMEOUT_MS;
};

export const broadcastAuthEvent = (payload: Omit<AuthEventPayload, 'at'>) => {
  const event: AuthEventPayload = { ...payload, at: now() };
  window.dispatchEvent(new CustomEvent<AuthEventPayload>('studyspace-auth', { detail: event }));
  try {
    localStorage.setItem(AUTH_EVENT_KEY, JSON.stringify(event));
  } catch {
    // Storage may be unavailable in strict/private modes.
  }
};

export const recordActivity = (source: 'user' | 'route' | 'api' = 'user') => {
  if (!getAccessToken()) return;
  localStorage.setItem(AUTH_LAST_ACTIVITY_KEY, String(now()));
  if (source !== 'api') {
    broadcastAuthEvent({ type: 'activity' });
  }
};

export const persistAuthSessionFromResponse = (data: any) => {
  const user = tokenResponseToUser(data);
  localStorage.setItem(AUTH_TOKEN_KEY, data.access_token);
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  localStorage.setItem(AUTH_LAST_ACTIVITY_KEY, String(now()));
  if (data.refresh_token_expires_at) {
    localStorage.setItem(AUTH_REFRESH_EXPIRES_KEY, data.refresh_token_expires_at);
  }
  broadcastAuthEvent({ type: 'login' });
  return user;
};

export const updateStoredAccessSession = (data: any) => {
  if (data.access_token) {
    localStorage.setItem(AUTH_TOKEN_KEY, data.access_token);
  }
  if (data.refresh_token_expires_at) {
    localStorage.setItem(AUTH_REFRESH_EXPIRES_KEY, data.refresh_token_expires_at);
  }
  const existing = getStoredUser();
  const user = data.user_id ? tokenResponseToUser(data) : existing;
  if (user) {
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  }
  recordActivity('api');
  broadcastAuthEvent({ type: 'session-refreshed' });
  return user;
};

export const updateStoredUser = (user: any) => {
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  broadcastAuthEvent({ type: 'session-refreshed' });
};

export const clearAuthSession = (
  reason: string = 'logout',
  options: { broadcast?: boolean; redirectTo?: string } = {},
) => {
  if (options.redirectTo) {
    savePendingRedirect(options.redirectTo);
  }
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
  localStorage.removeItem(AUTH_LAST_ACTIVITY_KEY);
  localStorage.removeItem(AUTH_REFRESH_EXPIRES_KEY);
  sessionStorage.removeItem('csrf_token');
  sessionStorage.removeItem('boost_payment_callback');

  if (options.broadcast !== false) {
    broadcastAuthEvent({ type: 'logout', reason, redirectTo: options.redirectTo });
  }
};

export const isAuthRoute = (path: string): boolean =>
  path === '/login' || path === '/auth' || path === '/register';

export const isProtectedPath = (path: string): boolean =>
  Boolean(path && path !== '/' && !isAuthRoute(path) && !path.startsWith('/mock-payment'));

export const savePendingRedirect = (path: string) => {
  if (isProtectedPath(path)) {
    sessionStorage.setItem(AUTH_PENDING_REDIRECT_KEY, path);
  }
};

export const getPendingRedirect = () => sessionStorage.getItem(AUTH_PENDING_REDIRECT_KEY);

export const clearPendingRedirect = () => sessionStorage.removeItem(AUTH_PENDING_REDIRECT_KEY);

export const roleHomePath = (role: UserRole, email?: string): string => {
  if (email === 'superadmin@studyspace.com' || role === UserRole.SUPER_ADMIN) return '/super-admin';
  if (role === UserRole.ADMIN) return '/admin';
  return '/student';
};

export const isRedirectAllowedForRole = (path: string | null, role: UserRole): boolean => {
  if (!path || !isProtectedPath(path)) return false;
  if (role === UserRole.SUPER_ADMIN) return path.startsWith('/super-admin') || path === '/support';
  if (role === UserRole.ADMIN) return path.startsWith('/admin') || path === '/support';
  if (role === UserRole.STUDENT) return path.startsWith('/student') || path === '/support';
  return false;
};

export const getPostLoginRedirect = (role: UserRole, email?: string): string => {
  const pending = getPendingRedirect();
  if (isRedirectAllowedForRole(pending, role)) {
    clearPendingRedirect();
    return pending!;
  }
  clearPendingRedirect();
  return roleHomePath(role, email);
};

export const canRestoreStoredSession = (): boolean =>
  Boolean(getAccessToken() && getStoredUser() && !isRefreshSessionExpired() && !isInactive());
