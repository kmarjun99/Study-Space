/**
 * Intelligence profile service (Phase 2).
 *
 * Reads derived profile rows. Writes here are super-admin-only triggers
 * for manual rebuilds; the daily cron does the routine work.
 */
import api from './api';

export type IntentLevel =
  | 'LOW_INTENT' | 'MEDIUM_INTENT' | 'HIGH_INTENT' | 'HOT_LEAD';

export interface IntelligenceProfile {
  user_id: string;
  preferred_city: string | null;
  preferred_locations: string[];
  preferred_property_types: string[];
  preferred_amenities: string[];
  preferred_price_min: number | null;
  preferred_price_max: number | null;
  preferred_study_time: string | null;
  booking_urgency_score: number;
  budget_sensitivity_score: number;
  location_sensitivity_score: number;
  premium_interest_score: number;
  cancellation_risk_score: number;
  conversion_probability_score: number;
  raw_intent_score: number;
  intent_level: IntentLevel;
  last_active_at: string | null;
  last_search_query: string | null;
  last_viewed_listing_id: string | null;
  last_booking_attempt_at: string | null;
  last_successful_booking_at: string | null;
  profile_confidence_score: number;
  event_count: number;
  updated_at: string;
}

export const intelligenceService = {
  async getMyProfile(): Promise<IntelligenceProfile | null> {
    const res = await api.get<IntelligenceProfile | null>(
      '/api/users/me/intelligence-profile',
    );
    return res.data;
  },
  async listProfiles(
    level?: IntentLevel,
    limit = 100,
    offset = 0,
  ): Promise<IntelligenceProfile[]> {
    const res = await api.get<IntelligenceProfile[]>(
      '/api/super-admin/intelligence/profiles',
      { params: { level, limit, offset } },
    );
    return res.data;
  },
  async rebuildForUser(userId: string): Promise<unknown> {
    const res = await api.post('/api/super-admin/intelligence/rebuild', {
      user_id: userId,
    });
    return res.data;
  },
  async rebuildAll(sinceDays = 1): Promise<unknown> {
    const res = await api.post('/api/super-admin/intelligence/rebuild', {
      since_days: sinceDays,
    });
    return res.data;
  },
};
