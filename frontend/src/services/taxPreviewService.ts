/**
 * Tax preview — pure read endpoint that returns the GST split a student
 * would see for a given listing + displayed price. Does not write anything.
 */
import api from './api';

export type GstTreatment =
  | 'OWNER_REGISTERED'
  | 'SEC_9_5'
  | 'EXEMPT'
  | 'NOT_REGISTERED';

export interface TaxPreviewRequest {
  listing_type: 'reading-room' | 'accommodation';
  listing_id: string;
  displayed_price: number;
  place_of_supply_state?: string | null;
}

export interface TaxPreviewResponse {
  payable_amount: number;
  base_amount: number;
  gst_amount: number;
  cgst: number;
  sgst: number;
  igst: number;
  gst_rate_applied: number;
  treatment: GstTreatment | string;
  effective_mode: 'GST_INCLUDED' | 'GST_EXTRA';
  listing_mode: string | null;
  per_listing_flag_on: boolean;
  notes: string[];
}

export const taxPreviewService = {
  async preview(req: TaxPreviewRequest): Promise<TaxPreviewResponse> {
    const res = await api.post<TaxPreviewResponse>('/api/tax/preview-booking', req);
    return res.data;
  },
};
