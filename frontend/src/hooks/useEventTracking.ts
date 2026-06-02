/**
 * useEventTracking — React hook wrapper around eventService.
 *
 * Returns a stable `track` callback that closes over no state, so it can be
 * dropped into useEffect dependency arrays without causing re-renders.
 *
 * Keeps the eventService API thin and pure JS; this hook just exists to
 * make component-level wiring ergonomic.
 */
import { useCallback } from 'react';
import { eventService, TrackPayload } from '../services/eventService';

export function useEventTracking() {
  const track = useCallback((payload: TrackPayload) => {
    eventService.track(payload);
  }, []);

  return { track };
}
