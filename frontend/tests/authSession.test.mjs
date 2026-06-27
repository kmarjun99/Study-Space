import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import { transformSync } from 'esbuild';

const root = path.resolve(import.meta.dirname, '..');
const source = fs.readFileSync(path.join(root, 'src/utils/authSession.ts'), 'utf8');
const compiled = transformSync(source, {
  loader: 'ts',
  format: 'cjs',
  platform: 'node',
}).code;

const createStorage = () => {
  const store = new Map();
  return {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: (key) => store.delete(key),
    clear: () => store.clear(),
    _dump: () => Object.fromEntries(store.entries()),
  };
};

const makeToken = (expSeconds) => {
  const encode = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ sub: 'owner@example.com', exp: expSeconds })}.sig`;
};

const loadModule = () => {
  const module = { exports: {} };
  const localStorage = createStorage();
  const sessionStorage = createStorage();
  const context = {
    module,
    exports: module.exports,
    require: (id) => {
      if (id === '../types') {
        return { UserRole: { STUDENT: 'STUDENT', ADMIN: 'ADMIN', SUPER_ADMIN: 'SUPER_ADMIN' } };
      }
      throw new Error(`Unexpected require: ${id}`);
    },
    window: {
      atob: (value) => Buffer.from(value, 'base64').toString('binary'),
      dispatchEvent: () => true,
    },
    CustomEvent: class CustomEvent {
      constructor(type, init) {
        this.type = type;
        this.detail = init?.detail;
      }
    },
    localStorage,
    sessionStorage,
    Date,
  };
  vm.runInNewContext(compiled, context);
  return { auth: module.exports, localStorage, sessionStorage };
};

test('persistAuthSessionFromResponse stores token, user, activity, and refresh expiry', () => {
  const { auth, localStorage } = loadModule();
  const response = {
    access_token: makeToken(Math.floor(Date.now() / 1000) + 1800),
    user_id: 'u-1',
    name: 'Owner',
    email: 'owner@example.com',
    role: 'ADMIN',
    avatar_url: '/avatar.png',
    has_active_waitlist: false,
    refresh_token_expires_at: '2026-07-08T00:00:00Z',
  };

  const user = auth.persistAuthSessionFromResponse(response);

  assert.equal(user.id, 'u-1');
  assert.equal(localStorage.getItem(auth.AUTH_TOKEN_KEY), response.access_token);
  assert.equal(JSON.parse(localStorage.getItem(auth.AUTH_USER_KEY)).email, 'owner@example.com');
  assert.ok(Number(localStorage.getItem(auth.AUTH_LAST_ACTIVITY_KEY)) > 0);
  assert.equal(localStorage.getItem(auth.AUTH_REFRESH_EXPIRES_KEY), response.refresh_token_expires_at);
});

test('JWT expiry and refresh skew are detected', () => {
  const { auth } = loadModule();
  const expired = makeToken(Math.floor(Date.now() / 1000) - 5);
  const valid = makeToken(Math.floor(Date.now() / 1000) + 1800);
  const almostExpired = makeToken(Math.floor(Date.now() / 1000) + 30);

  assert.equal(auth.isAccessTokenExpired(expired), true);
  assert.equal(auth.isAccessTokenExpired(valid), false);
  assert.equal(auth.shouldRefreshAccessToken(almostExpired), true);
});

test('inactivity timeout and warning windows are enforced', () => {
  const { auth, localStorage } = loadModule();
  const originalNow = Date.now;
  const base = 1_800_000_000_000;
  Date.now = () => base;
  localStorage.setItem(auth.AUTH_TOKEN_KEY, 'token');
  auth.recordActivity('user');

  Date.now = () => base + auth.INACTIVITY_TIMEOUT_MS - auth.INACTIVITY_WARNING_MS + 1;
  assert.equal(auth.shouldShowInactivityWarning(), true);
  assert.equal(auth.isInactive(), false);

  Date.now = () => base + auth.INACTIVITY_TIMEOUT_MS + 1;
  assert.equal(auth.isInactive(), true);
  Date.now = originalNow;
});

test('pending redirects return users only to role-allowed protected pages', () => {
  const { auth, sessionStorage } = loadModule();

  auth.savePendingRedirect('/admin/venue/123');
  assert.equal(auth.getPostLoginRedirect('ADMIN', 'owner@example.com'), '/admin/venue/123');
  assert.equal(sessionStorage.getItem(auth.AUTH_PENDING_REDIRECT_KEY), null);

  auth.savePendingRedirect('/admin/venue/123');
  assert.equal(auth.getPostLoginRedirect('STUDENT', 'student@example.com'), '/student');
});

test('clearAuthSession removes protected auth and transient protected state', () => {
  const { auth, localStorage, sessionStorage } = loadModule();
  localStorage.setItem(auth.AUTH_TOKEN_KEY, 'token');
  localStorage.setItem(auth.AUTH_USER_KEY, '{}');
  localStorage.setItem(auth.AUTH_LAST_ACTIVITY_KEY, '1');
  localStorage.setItem(auth.AUTH_REFRESH_EXPIRES_KEY, '2026-07-08T00:00:00Z');
  sessionStorage.setItem('csrf_token', 'csrf');
  sessionStorage.setItem('boost_payment_callback', '{}');

  auth.clearAuthSession('logout', { broadcast: false });

  assert.equal(localStorage.getItem(auth.AUTH_TOKEN_KEY), null);
  assert.equal(localStorage.getItem(auth.AUTH_USER_KEY), null);
  assert.equal(localStorage.getItem(auth.AUTH_LAST_ACTIVITY_KEY), null);
  assert.equal(localStorage.getItem(auth.AUTH_REFRESH_EXPIRES_KEY), null);
  assert.equal(sessionStorage.getItem('csrf_token'), null);
  assert.equal(sessionStorage.getItem('boost_payment_callback'), null);
});

test('clearAuthSession broadcasts logout for multi-tab sync', () => {
  const { auth, localStorage } = loadModule();
  localStorage.setItem(auth.AUTH_TOKEN_KEY, 'token');

  auth.clearAuthSession('expired', { redirectTo: '/admin' });

  const event = JSON.parse(localStorage.getItem(auth.AUTH_EVENT_KEY));
  assert.equal(event.type, 'logout');
  assert.equal(event.reason, 'expired');
  assert.equal(event.redirectTo, '/admin');
});
