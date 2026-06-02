/**
 * Campaign service — super-admin CRUD + delivery list + funnel.
 */
import api from './api';

export type CampaignChannel = 'IN_APP' | 'EMAIL' | 'PUSH' | 'WHATSAPP';
export type CampaignStatus = 'DRAFT' | 'ACTIVE' | 'PAUSED' | 'COMPLETED';
export type DeliveryStatus =
  | 'QUEUED' | 'DELIVERED' | 'FAILED'
  | 'SKIPPED_COOLDOWN' | 'SKIPPED_FREQUENCY' | 'SKIPPED_CONSENT';

export interface Campaign {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  body_template: string;
  segment_id: string;
  channel: CampaignChannel;
  status: CampaignStatus;
  cooldown_hours: number;
  frequency_cap_per_user: number;
  frequency_cap_window_days: number;
  send_window_starts: string | null;
  send_window_ends: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignInput {
  slug: string;
  name: string;
  description?: string;
  body_template: string;
  segment_id: string;
  channel: CampaignChannel;
  cooldown_hours?: number;
  frequency_cap_per_user?: number;
  frequency_cap_window_days?: number;
  send_window_starts?: string;
  send_window_ends?: string;
}

export interface CampaignPatch {
  name?: string;
  description?: string;
  body_template?: string;
  status?: CampaignStatus;
  cooldown_hours?: number;
  frequency_cap_per_user?: number;
  frequency_cap_window_days?: number;
  send_window_starts?: string;
  send_window_ends?: string;
}

export interface Delivery {
  id: string;
  campaign_id: string;
  user_id: string;
  channel: CampaignChannel;
  status: DeliveryStatus;
  queued_at: string;
  delivered_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
  converted_at: string | null;
  converted_booking_id: string | null;
  reason: string | null;
}

export interface Funnel {
  campaign_id: string;
  queued: number;
  delivered: number;
  opened: number;
  clicked: number;
  converted: number;
  skipped_consent: number;
  skipped_cooldown: number;
  skipped_frequency: number;
  failed: number;
}

export interface EnqueueSummary {
  queued: number;
  skipped_consent: number;
  skipped_cooldown: number;
  skipped_frequency: number;
  reasons: string[];
}

export const campaignService = {
  async list(includeCompleted = true): Promise<Campaign[]> {
    const res = await api.get<Campaign[]>('/api/super-admin/campaigns', {
      params: { include_completed: includeCompleted },
    });
    return res.data;
  },
  async create(input: CampaignInput): Promise<Campaign> {
    const res = await api.post<Campaign>('/api/super-admin/campaigns', input);
    return res.data;
  },
  async patch(id: string, body: CampaignPatch): Promise<Campaign> {
    const res = await api.patch<Campaign>(`/api/super-admin/campaigns/${id}`, body);
    return res.data;
  },
  async enqueue(id: string): Promise<EnqueueSummary> {
    const res = await api.post<EnqueueSummary>(`/api/super-admin/campaigns/${id}/enqueue`);
    return res.data;
  },
  async deliveries(
    id: string, status?: DeliveryStatus, limit = 200,
  ): Promise<Delivery[]> {
    const res = await api.get<Delivery[]>(
      `/api/super-admin/campaigns/${id}/deliveries`,
      { params: { status, limit } },
    );
    return res.data;
  },
  async funnel(id: string): Promise<Funnel> {
    const res = await api.get<Funnel>(`/api/super-admin/campaigns/${id}/funnel`);
    return res.data;
  },
};
