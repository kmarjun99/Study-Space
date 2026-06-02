/**
 * Recommendation service — four read surfaces.
 *
 * Returns [] silently when the backend has recommendations disabled or the
 * caller is missing consent. The UI hides the section in that case rather
 * than showing an error.
 */
import api from './api';

export interface Recommendation {
  listing_type: 'reading_room' | 'accommodation';
  listing_id: string;
  name: string;
  city: string | null;
  state: string | null;
  price: number | null;
  rank: number;
  score: number;
  reason_code: string;
  extra: {
    is_sponsored?: boolean;
    admin_priority?: number | null;
  };
}

async function safeFetch(path: string, params?: Record<string, unknown>): Promise<Recommendation[]> {
  try {
    const res = await api.get<Recommendation[]>(path, { params });
    return res.data;
  } catch (e: any) {
    // 401/403/404 -> silently return empty so the UI just hides the slot.
    return [];
  }
}

export const recommendationService = {
  forMe(limit = 10): Promise<Recommendation[]> {
    return safeFetch('/api/recommendations/for-me', { limit });
  },
  similar(
    listingType: 'reading_room' | 'accommodation',
    listingId: string,
    limit = 10,
  ): Promise<Recommendation[]> {
    return safeFetch('/api/recommendations/similar', {
      listing_type: listingType, listing_id: listingId, limit,
    });
  },
  trending(city?: string, windowDays = 7, limit = 10): Promise<Recommendation[]> {
    return safeFetch('/api/recommendations/trending', {
      city, window_days: windowDays, limit,
    });
  },
  recentlyViewed(limit = 10): Promise<Recommendation[]> {
    return safeFetch('/api/recommendations/recently-viewed', { limit });
  },
  // Super-admin
  async setPriority(
    listingType: 'reading_room' | 'accommodation',
    listingId: string,
    body: {
      recommendation_priority?: number | null;
      recommendation_excluded?: boolean;
      clear_priority?: boolean;
    },
  ): Promise<unknown> {
    const res = await api.patch(
      `/api/super-admin/listings/${listingType}/${listingId}/recommendation`,
      body,
    );
    return res.data;
  },
};
