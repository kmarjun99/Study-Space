/**
 * Behavioral event tracker.
 *
 * Fire-and-forget client for the Phase 1 event firehose. Provides:
 *   - Persistent anonymous_session_id in localStorage
 *   - In-memory queue with periodic flush (debounced) to /events/batch
 *   - Manual flush() for navigation-away scenarios
 *   - track(name, category, payload) — primary API
 *   - deleteMyEvents() — right-to-erasure
 *
 * Designed to NEVER throw or block the UI. Backend may drop the event
 * silently (consent / master flag off) — the client doesn't try to
 * reconcile that. UI just calls track() and forgets.
 */
import api from './api';

const STORAGE_KEY = 'studySpace_anonSessionId';
const FLUSH_MS = 2000;
const MAX_BATCH = 50;

type EventCategory =
  | 'SEARCH' | 'VIEW' | 'FILTER' | 'INTENT' | 'BOOKING' | 'PAYMENT'
  | 'SAVE' | 'COMPARE' | 'CONTACT' | 'AD' | 'NOTIFICATION'
  | 'CANCELLATION' | 'REFUND' | 'SYSTEM';

type EntityType =
  | 'reading_room' | 'cabin' | 'accommodation' | 'offer'
  | 'search' | 'booking' | 'ad' | 'notification' | 'refund';

export interface TrackPayload {
  event_id?: string;             // client supplies; we generate one if missing
  event_name: string;
  event_category: EventCategory;
  entity_type?: EntityType;
  entity_id?: string;
  metadata?: Record<string, unknown>;
  source_page?: string;
  city?: string;
  location_query?: string;
}

interface QueuedEvent extends TrackPayload {
  event_id: string;
  anonymous_session_id: string;
  device_type: string;
  platform: 'web';
  referrer?: string;
  source_page?: string;
}

const _queue: QueuedEvent[] = [];
let _flushTimer: number | null = null;

const _genId = (): string =>
  // Cheap UUID-ish; collision-safe enough for client idempotency keys.
  // The server uses `event_id` as a unique constraint so true collisions
  // are dropped as duplicates anyway.
  `evt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

const _ensureSessionId = (): string => {
  if (typeof window === 'undefined') return 'noop';
  let v = localStorage.getItem(STORAGE_KEY);
  if (!v) {
    v = `sess-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
    try { localStorage.setItem(STORAGE_KEY, v); } catch { /* private mode etc. */ }
  }
  return v;
};

const _deviceType = (): string => {
  if (typeof window === 'undefined') return 'unknown';
  const w = window.innerWidth || 0;
  if (w >= 1024) return 'desktop';
  if (w >= 640) return 'tablet';
  return 'mobile';
};

async function _flush(): Promise<void> {
  if (_queue.length === 0) return;
  const batch = _queue.splice(0, MAX_BATCH);
  try {
    await api.post('/api/events/batch', { events: batch });
  } catch {
    // Swallow — event ingest must never block UX. We do NOT requeue
    // because that would amplify load when the backend is down.
  }
}

function _scheduleFlush(): void {
  if (_flushTimer !== null) return;
  _flushTimer = window.setTimeout(() => {
    _flushTimer = null;
    void _flush();
  }, FLUSH_MS);
}

export const eventService = {
  track(payload: TrackPayload): void {
    try {
      const evt: QueuedEvent = {
        ...payload,
        event_id: payload.event_id ?? _genId(),
        anonymous_session_id: _ensureSessionId(),
        device_type: _deviceType(),
        platform: 'web',
        referrer: typeof document !== 'undefined' ? document.referrer : undefined,
        source_page: payload.source_page
          ?? (typeof window !== 'undefined' ? window.location.pathname : undefined),
      };
      _queue.push(evt);
      if (_queue.length >= MAX_BATCH) {
        void _flush();
      } else {
        _scheduleFlush();
      }
    } catch {
      // Any unexpected error is silenced — tracking never breaks the app.
    }
  },

  /** Flush immediately. Call on logout, route change, or beforeunload. */
  async flush(): Promise<void> {
    if (_flushTimer !== null) {
      clearTimeout(_flushTimer);
      _flushTimer = null;
    }
    await _flush();
  },

  /** Right-to-erasure. Wipes the anonymous session id too. */
  async deleteMyEvents(): Promise<{ deleted: number }> {
    const res = await api.delete<{ deleted: number }>('/api/events/me');
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* noop */ }
    return res.data;
  },

  /** List recent events for the user (transparency surface). */
  async listMyRecentEvents(limit = 100): Promise<unknown[]> {
    const res = await api.get('/api/events/me', { params: { limit } });
    return res.data as unknown[];
  },
};

// Best-effort flush when the user navigates away.
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => { void _flush(); });
}
