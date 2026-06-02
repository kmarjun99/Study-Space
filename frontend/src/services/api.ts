
import axios from 'axios';



// Resolve the backend base URL for axios.
//
// Three regimes:
//   1. VITE_API_BASE_URL is set at build time → use it as-is. Used by
//      deployments that proxy through a separate API origin.
//   2. Running on localhost / 127.0.0.1 (dev) → talk to the local
//      FastAPI on :8000.
//   3. Anywhere else (production, staging, network-IP dev on mobile)
//      → return EMPTY STRING. axios then issues requests against the
//      same origin, e.g. `api.get('/auth/login')` becomes
//      https://myspaceapp.in/auth/login, which nginx/Cloud Load Balancer
//      proxies to the backend Cloud Run service.
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
  const fromEnv = import.meta.env.VITE_API_BASE_URL;
  if (fromEnv) return fromEnv;

  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8000';
    }
    // Production / any non-local host: use relative URLs so requests
    // inherit the page's protocol (HTTPS) and port (443), and let the
    // load balancer route by path.
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
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add a request interceptor
api.interceptors.request.use(
  (config) => {
    // Get the token from local storage
    const token = localStorage.getItem('studySpace_token');
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
  (error) => {
    if (error.response && error.response.status === 401) {
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
        console.warn(
          'Session expired or token rejected. Clearing auth data… detail:',
          detail ?? '(none)',
        );
        localStorage.removeItem('studySpace_token');
        localStorage.removeItem('studySpace_user');
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
