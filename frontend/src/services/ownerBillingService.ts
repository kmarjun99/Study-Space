/**
 * Owner Billing Service.
 * Talks to the new /owner/charges API for one-time listing fees and recurring
 * monthly maintenance fees. Mirrors the existing paymentService.ts pattern.
 */
import api from './api';

export type OwnerChargeType =
  | 'LISTING_FEE'
  | 'MAINTENANCE_FEE'
  | 'FACILITATION_FEE'
  | 'RECOVERY';

export type OwnerChargeStatus =
  | 'DRAFT'
  | 'DUE'
  | 'PAID'
  | 'WAIVED'
  | 'FAILED'
  | 'OVERDUE';

export interface OwnerCharge {
  id: string;
  owner_id: string;
  listing_id: string | null;
  listing_type: 'READING_ROOM' | 'ACCOMMODATION' | null;
  charge_type: OwnerChargeType;
  period_key: string | null;        // 'YYYY-MM' for recurring
  base_amount: number;
  gst_amount: number;
  total_amount: number;
  gst_rate_applied: number | null;
  status: OwnerChargeStatus;
  due_date: string | null;
  invoice_id: string | null;
  razorpay_payment_id: string | null;
  created_at: string;
  paid_at: string | null;
}

export interface ChargePayOrder {
  order_id: string;
  amount: number;             // paise
  currency: string;
  razorpay_key_id: string;
  is_demo: boolean;
  charge_id: string;
}

export interface ChargeInvoice {
  invoice_number: string;
  doc_type: string | null;
  series_code: string | null;
  fiscal_year: string | null;
  sequence_no: number | null;
  base_amount: number | null;
  cgst: number;
  sgst: number;
  igst: number;
  total_amount: number;
  hsn_sac: string | null;
  place_of_supply_state: string | null;
  generated_at: string;
}

export const ownerBillingService = {
  async listCharges(status?: OwnerChargeStatus): Promise<OwnerCharge[]> {
    const res = await api.get<OwnerCharge[]>('/api/owner/charges', {
      params: status ? { status } : undefined,
    });
    return res.data;
  },

  async createListingFee(input: {
    listing_id: string;
    listing_type: 'READING_ROOM' | 'ACCOMMODATION';
    plan_id: string;
  }): Promise<OwnerCharge> {
    const res = await api.post<OwnerCharge>('/api/owner/charges/listing-fee', input);
    return res.data;
  },

  async createPayOrder(chargeId: string): Promise<ChargePayOrder> {
    const res = await api.post<ChargePayOrder>(`/api/owner/charges/${chargeId}/pay-order`);
    return res.data;
  },

  /**
   * Client-side confirmation. The webhook is the source of truth, but this
   * endpoint exists so the UI can show immediate feedback.
   */
  async confirmPayment(chargeId: string, razorpayPaymentId: string): Promise<OwnerCharge> {
    const res = await api.post<OwnerCharge>(`/api/owner/charges/${chargeId}/confirm`, {
      razorpay_payment_id: razorpayPaymentId,
    });
    return res.data;
  },

  async getInvoice(chargeId: string): Promise<ChargeInvoice> {
    const res = await api.get<ChargeInvoice>(`/api/owner/charges/${chargeId}/invoice`);
    return res.data;
  },

  /**
   * Fetch the platform tax invoice PDF for a paid charge and trigger a
   * browser download. Mirrors paymentService.downloadInvoice for bookings.
   * Backend endpoint: GET /api/owner/charges/{id}/invoice/pdf
   */
  async downloadInvoicePdf(chargeId: string): Promise<void> {
    const res = await api.get(`/api/owner/charges/${chargeId}/invoice/pdf`, {
      responseType: 'blob',
      timeout: 60_000,
    });
    const blob = new Blob([res.data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    // Prefer the filename the backend hands back in Content-Disposition; fall
    // back to a short charge-id slug so paid charges still get a sensible name.
    const disposition = res.headers['content-disposition'] as string | undefined;
    let filename = `Invoice_${chargeId.slice(0, 8)}.pdf`;
    if (disposition) {
      const match = disposition.match(/filename="?([^";]+)"?/);
      if (match?.[1]) filename = match[1];
    }
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};
