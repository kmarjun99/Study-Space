/**
 * Per-listing billing config (owner sets gst_category, gst_rate_override,
 * gst_sac, price_display_mode, billing_anchor_day).
 *
 * Note: `price_display_mode` is informational until the platform flag
 * `feature.per_listing_price_mode` is enabled by super-admin. The UI must
 * surface that state to the owner so they don't expect the change to take
 * effect immediately.
 */
import api from './api';

export type ListingTypeSlug = 'reading-room' | 'accommodation';
export type GstCategory =
  | 'HOTEL_LIKE'
  | 'SHORT_STAY'
  | 'HOSTEL_PG'
  | 'READING_ROOM'
  | 'OTHER';
export type PriceDisplayMode = 'GST_INCLUDED' | 'GST_EXTRA';

export interface BillingConfig {
  listing_type: string;
  listing_id: string;
  gst_category: GstCategory | null;
  gst_rate_override: number | null;     // 0–1 (e.g. 0.18)
  gst_sac: string | null;
  price_display_mode: PriceDisplayMode | null;
  billing_anchor_day: number | null;
  maintenance_status: string | null;
}

export interface BillingConfigUpdate {
  gst_category?: GstCategory | null;
  gst_rate_override?: number | null;
  gst_sac?: string | null;
  price_display_mode?: PriceDisplayMode | null;
  billing_anchor_day?: number | null;
  // Pydantic can't tell "missing" from "null" so we send explicit clear flags.
  clear_gst_category?: boolean;
  clear_gst_rate_override?: boolean;
  clear_price_display_mode?: boolean;
}

export const listingBillingService = {
  async get(type: ListingTypeSlug, id: string): Promise<BillingConfig> {
    const res = await api.get<BillingConfig>(
      `/api/owner/listings/${type}/${id}/billing-config`,
    );
    return res.data;
  },

  async update(
    type: ListingTypeSlug,
    id: string,
    body: BillingConfigUpdate,
  ): Promise<BillingConfig> {
    const res = await api.patch<BillingConfig>(
      `/api/owner/listings/${type}/${id}/billing-config`,
      body,
    );
    return res.data;
  },
};
