/**
 * Hover-triggered prefetch for lazy route chunks.
 *
 * App.tsx code-splits ~50 routes via React.lazy(). Each click on a nav
 * link blocks the user on a network round-trip while the chunk loads.
 * This module exposes prefetchRoute(href) which fires the matching
 * dynamic import() the moment the user hovers a link, so by the time
 * they click the JS is already cached.
 *
 * Critical: the preloader functions in `ROUTE_PRELOADERS` are the EXACT
 * SAME closures React.lazy() uses internally for each component. That
 * shared identity is what makes prefetch + click cooperate cleanly:
 *
 *   * Hover → preload runs → React.lazy's internal `_payload._status`
 *     advances to 1 (resolved) with the module cached.
 *   * Click → React.lazy reads `_payload._status === 1` → returns
 *     synchronously, no second import, no flicker.
 *
 *   * If preload fails → React.lazy's `_payload._status` becomes 2
 *     (rejected) with the actual error. On the subsequent click,
 *     React throws into the nearest ErrorBoundary, surfacing a real
 *     error UI instead of leaving the previous page mounted.
 *
 * Previous version maintained a separate `LOADERS` map that called
 * `import()` independently of React.lazy. A failed prefetch poisoned
 * the browser's module map; the eventual lazy() call got the cached
 * rejection but had no error boundary in scope, so the OLD page stayed
 * visible at the new URL — the "URL changes but tab content doesn't
 * load" bug.
 */

import { ROUTE_PRELOADERS } from '../App';

// Track succeeded paths so we don't re-trigger preload on every hover.
// (React.lazy memoizes too, but skipping the function call entirely is
// nicer for the React profiler and for our intent-tracking.)
const warmed = new Set<string>();

export const prefetchRoute = (href: string): void => {
    if (warmed.has(href)) return;
    const preload = ROUTE_PRELOADERS[href];
    if (!preload) return;
    // Fire-and-forget. preload() returns the same Promise React.lazy
    // awaits internally, so failures land in React.lazy's _payload and
    // surface via ErrorBoundary on the next render. We don't catch
    // here — silent catches hide failures that the user needs to see
    // (or that a developer needs to fix). Mark as warmed only on success
    // so a transient failure doesn't permanently block re-prefetch.
    void preload()
        .then(() => { warmed.add(href); })
        .catch(() => { /* let React.lazy own the error UX */ });
};
