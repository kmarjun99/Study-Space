/**
 * Phase 4D — recommendation attribution funnel.
 */
import api from './api';

export interface SurfaceFunnel {
    surface: string;
    impressions: number;
    clicks: number;
    conversions: number;
    click_attributed_conversions: number;
    impression_attributed_conversions: number;
    ctr: number;
    cvr: number;
}

export interface AttributionFunnel {
    total_impressions: number;
    total_clicks: number;
    total_conversions: number;
    surfaces: SurfaceFunnel[];
}

export const recommendationAttributionService = {
    async funnel(): Promise<AttributionFunnel> {
        const res = await api.get<AttributionFunnel>(
            '/api/super-admin/recommendation-attribution/funnel',
        );
        return res.data;
    },

    /** Public — used by listing-card click handler to stamp the impression
     *  as clicked, so attribution upgrades to click-attributed. */
    async recordClick(logId: string): Promise<void> {
        await api.post(`/api/recommendation-logs/${logId}/clicked`);
    },
};
