
import axios from 'axios';
import {
  clearAuthSession,
  getAccessToken,
  recordActivity,
  shouldRefreshAccessToken,
  updateStoredAccessSession,
} from '../utils/authSession';



// Resolve the backend base URL for axios.
//
// Four regimes:
//   1. BACKEND_URL/VITE_API_BASE_URL is injected into env-config.js when the
//      production container starts → use it as-is.
//   2. VITE_API_BASE_URL is set at build time → use it as-is.
//   3. Running on localhost / 127.0.0.1 (dev) → talk to the local
//      FastAPI on :8000.
//   4. Anywhere else (production, staging, network-IP dev on mobile)
//      → return EMPTY STRING. axios then issues requests against the
//      same origin. This is only a final fallback for deployments with a
//      same-origin API proxy.
//
// The previous fallback returned `http://${hostname}:8000` — for prod
// hostname=myspaceapp.in that resolved to `http://myspaceapp.in:8000`,
// which is (a) HTTP not HTTPS so Chrome blocks it as mixed content on
// our HTTPS pages, and (b) port 8000 isn't even publicly exposed. Every
// API call from the SPA failed with "Mixed Content: ... blocked" and
// the user was unable to log in. Same-origin relative URLs avoid both
// problems: the browser uses the page's HTTPS scheme and the load
// balancer routes by path.
const getBaseUrl = (): string => {
  const runtimeUrl =
    typeof window !== 'undefined'
      ? window.__MYSPACE_RUNTIME_CONFIG__?.API_BASE_URL?.trim()
      : undefined;
  if (runtimeUrl) return runtimeUrl.replace(/\/+$/, '');

  const fromEnv = import.meta.env.VITE_API_BASE_URL;
  if (fromEnv) return fromEnv.replace(/\/+$/, '');

  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8000';
    }
    // Production / any non-local host: use relative URLs only when the
    // deployment has intentionally configured a same-origin API proxy.
    return '';
  }

  // SSR / non-browser context — there's no `window`, so we can't use
  // the page origin. Fall back to localhost for build-time safety;
  // these requests never actually fire in this codebase.
  return 'http://localhost:8000';
};

const api = axios.create({
  baseURL: getBaseUrl(), // Backend URL
  timeout: 30000, // 30 seconds timeout (increased for complex operations)
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

let refreshPromise: Promise<string | null> | null = null;

const refreshAccessToken = async (): Promise<string | null> => {
  if (!refreshPromise) {
    refreshPromise = api
      .post('/auth/refresh', undefined, { skipAuthRefresh: true } as any)
      .then((response) => {
        updateStoredAccessSession(response.data);
        return response.data.access_token as string;
      })
      .catch((error) => {
        const redirectTo = window.location.pathname + window.location.search + window.location.hash;
        clearAuthSession('expired', { redirectTo });
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
};

// Add a request interceptor
api.interceptors.request.use(
  async (config) => {
    const skipAuthRefresh = Boolean((config as any).skipAuthRefresh);
    if (!skipAuthRefresh) {
      recordActivity('api');
    }

    // Get the token from local storage. If it is close to expiring, refresh it
    // before the request so active users are not logged out while working.
    let token = getAccessToken();
    if (token && !skipAuthRefresh && shouldRefreshAccessToken(token)) {
      token = await refreshAccessToken();
    }

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },

  (error) => {
    return Promise.reject(error);
  }
);

// Add a response interceptor to handle 401s (Token Expiry).
//
// Tightened from "log out on ANY 401" to "log out only when the 401 is
// actually about authentication". The old behavior would clear the
// session whenever any endpoint returned 401 — which sometimes happens
// for valid sessions on:
//   * an old booking the user no longer has access to
//   * a transient race between a JWT refresh and a request firing
//   * an endpoint that mis-routes 401 instead of the proper 403
// Logging the user out on those errors was a UX trap. Now we only
// clear the session when the backend tells us the TOKEN itself is
// rejected (the get_current_user dependency in deps.py prefixes those
// detail messages with "Token rejected:" or returns the FastAPI
// default "Not authenticated").
//
// DO NOT redirect here - just clear the tokens and let React handle
// the auth state. Redirecting from an interceptor causes infinite
// loops when the page reloads.

const TOKEN_REJECT_PATTERNS = [
  /not authenticated/i,
  /token rejected/i,
  /could not validate credentials/i,
];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response && error.response.status === 401) {
      const originalRequest = error.config || {};
      // Inspect the body. If it names an auth issue, clear the session.
      // Otherwise leave the user signed in — the caller can show a
      // route-specific error.
      const detail: string | undefined =
        typeof error.response.data === 'object'
          ? error.response.data?.detail
          : undefined;

      const isTokenRejection =
        !detail || TOKEN_REJECT_PATTERNS.some(re => re.test(String(detail)));

      if (isTokenRejection) {
        if (!originalRequest._retry && !originalRequest.skipAuthRefresh) {
          originalRequest._retry = true;
          const newToken = await refreshAccessToken();
          if (newToken) {
            originalRequest.headers = originalRequest.headers || {};
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return api(originalRequest);
          }
        }

        console.warn(
          'Session expired or token rejected. Clearing auth data… detail:',
          detail ?? '(none)',
        );
        const redirectTo = window.location.pathname + window.location.search + window.location.hash;
        clearAuthSession('expired', { redirectTo });
        // React auth guard will show login page when appState.currentUser
        // becomes null on next rerender/refresh.
      } else {
        // 401 but NOT a token-rejection. Likely the endpoint is
        // mis-using 401 for an authorization issue, or the user is
        // momentarily off-network. Don't kill the session.
        console.warn(
          'Received 401 but token appears valid; leaving session intact. detail:',
          detail,
        );
      }
    }
    return Promise.reject(error);
  }
);


export default api;
