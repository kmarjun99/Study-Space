/**
 * Super-admin KYC review service.
 * Maps to /super-admin/owners/kyc endpoints.
 */
import api from './api';

export type KYCStatus = 'PENDING' | 'VERIFIED' | 'REJECTED' | 'NOT_REQUIRED';
export type GSTRegType = 'REGULAR' | 'COMPOSITION' | 'UNREGISTERED';

export interface OwnerKYCRow {
  id: string;
  email: string;
  name: string;
  legal_name: string | null;
  pan: string | null;
  gstin: string | null;
  gst_registration_type: GSTRegType | null;
  business_state_code: string | null;
  bank_account_holder: string | null;
  bank_account_number_masked: string | null;   // server masks to last 4
  bank_ifsc: string | null;
  kyc_status: KYCStatus | null;
  kyc_reviewed_by: string | null;
  kyc_reviewed_at: string | null;
  kyc_notes: string | null;
}

export const kycService = {
  async list(status?: KYCStatus): Promise<OwnerKYCRow[]> {
    const res = await api.get<OwnerKYCRow[]>('/api/super-admin/owners/kyc', {
      params: status ? { status } : undefined,
    });
    return res.data;
  },
  async get(ownerId: string): Promise<OwnerKYCRow> {
    const res = await api.get<OwnerKYCRow>(`/api/super-admin/owners/${ownerId}/kyc`);
    return res.data;
  },
  async approve(ownerId: string, notes?: string): Promise<OwnerKYCRow> {
    const res = await api.post<OwnerKYCRow>(
      `/api/super-admin/owners/${ownerId}/kyc/approve`,
      { notes: notes ?? null },
    );
    return res.data;
  },
  async reject(ownerId: string, notes: string): Promise<OwnerKYCRow> {
    const res = await api.post<OwnerKYCRow>(
      `/api/super-admin/owners/${ownerId}/kyc/reject`,
      { notes },
    );
    return res.data;
  },
  async requestReupload(ownerId: string, notes: string): Promise<OwnerKYCRow> {
    const res = await api.post<OwnerKYCRow>(
      `/api/super-admin/owners/${ownerId}/kyc/request-reupload`,
      { notes },
    );
    return res.data;
  },
};


// ---- Owner self-service KYC (the counterpart to the super-admin review) ----

export interface OwnerKYCMine {
  legal_name: string | null;
  pan: string | null;
  gstin: string | null;
  gst_registration_type: GSTRegType | null;
  business_state_code: string | null;
  bank_account_holder: string | null;
  bank_account_number_masked: string | null;
  bank_ifsc: string | null;
  kyc_status: KYCStatus | null;
  kyc_notes: string | null;          // reviewer feedback shown back to the owner
  kyc_reviewed_at: string | null;
}

export interface OwnerKYCSubmit {
  legal_name: string;
  gst_registration_type: GSTRegType;
  business_state_code: string;
  pan?: string | null;
  gstin?: string | null;
  bank_account_holder: string;
  bank_account_number: string;
  bank_ifsc: string;
}

export const ownerKycService = {
  /** The current owner's own KYC record (bank number masked). */
  async getMine(): Promise<OwnerKYCMine> {
    const res = await api.get<OwnerKYCMine>('/api/owner/kyc');
    return res.data;
  },
  /** Submit / update KYC. Moves the owner into the PENDING review queue. */
  async submitMine(data: OwnerKYCSubmit): Promise<OwnerKYCMine> {
    const res = await api.put<OwnerKYCMine>('/api/owner/kyc', data);
    return res.data;
  },
};
