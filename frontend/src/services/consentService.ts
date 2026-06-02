/**
 * User consent preference CRUD.
 */
import api from './api';

export interface ConsentPreferences {
  user_id: string;
  allow_analytics_tracking: boolean;
  allow_personalized_recommendations: boolean;
  allow_marketing_notifications: boolean;
  allow_whatsapp_updates: boolean;
  allow_location_based_suggestions: boolean;
  consent_policy_version: string | null;
  updated_at: string;
}

export interface ConsentUpdate {
  allow_analytics_tracking?: boolean;
  allow_personalized_recommendations?: boolean;
  allow_marketing_notifications?: boolean;
  allow_whatsapp_updates?: boolean;
  allow_location_based_suggestions?: boolean;
  consent_policy_version?: string;
  revoke_all?: boolean;
}

export const consentService = {
  async get(): Promise<ConsentPreferences> {
    const res = await api.get<ConsentPreferences>('/api/users/me/consent');
    return res.data;
  },
  async update(patch: ConsentUpdate): Promise<ConsentPreferences> {
    const res = await api.put<ConsentPreferences>('/api/users/me/consent', patch);
    return res.data;
  },
  async revokeAll(): Promise<ConsentPreferences> {
    const res = await api.put<ConsentPreferences>('/api/users/me/consent', { revoke_all: true });
    return res.data;
  },
};
