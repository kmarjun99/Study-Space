/**
 * Phase 5 — owner insights + super-admin dashboard.
 */
import api from './api';

export interface ListingInsight {
    listing_id: string;
    listing_type: string;
    name: string | null;
    impressions: number;
    clicks: number;
    views: number;
    saves: number;
    inquiries: number;
    bookings: number;
    distinct_viewers: number;
    view_to_inquiry_rate: number | null;
    view_to_booking_rate: number | null;
    low_volume_suppressed: boolean;
}

export interface OwnerInsights {
    enabled: boolean;
    owner_id: string;
    window_days?: number;
    total_impressions?: number;
    total_views?: number;
    total_saves?: number;
    total_inquiries?: number;
    total_bookings?: number;
    listings?: ListingInsight[];
    message?: string;
}

export interface FunnelStep { name: string; count: number; }
export interface CityDemand { city: string; searches: number; distinct_users: number; }
export interface SegmentSnapshot {
    segment_id: string; slug: string; name: string; active_members: number;
}
export interface CampaignSnapshot {
    campaign_id: string; slug: string; status: string;
    queued: number; delivered: number; clicked: number; converted: number;
}
export interface AutomationSnapshot {
    active_rules: number;
    queued_total: number;
    delivered_total: number;
    failed_total: number;
}
export interface AdminDashboard {
    enabled: boolean;
    window_days?: number;
    funnel?: FunnelStep[];
    top_cities?: CityDemand[];
    segments?: SegmentSnapshot[];
    campaigns?: CampaignSnapshot[];
    automation?: AutomationSnapshot;
}

export const insightsService = {
    async ownerInsights(windowDays = 30): Promise<OwnerInsights> {
        const res = await api.get<OwnerInsights>('/api/owner/insights', {
            params: { window_days: windowDays },
        });
        return res.data;
    },
    async adminDashboard(windowDays = 30): Promise<AdminDashboard> {
        const res = await api.get<AdminDashboard>('/api/super-admin/dashboard', {
            params: { window_days: windowDays },
        });
        return res.data;
    },
};
