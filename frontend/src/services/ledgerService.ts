/**
 * Super-admin ledger explorer service.
 * Maps to /super-admin/ledger endpoints.
 */
import api from './api';

export interface LedgerRow {
  id: string;
  posted_at: string;
  txn_group_id: string;
  account_code: string;
  party_type: string | null;
  party_id: string | null;
  debit: number;
  credit: number;
  currency: string;
  source_type: string;
  source_id: string;
  narration: string | null;
}

export interface LedgerPage {
  rows: LedgerRow[];
  total: number;
  sum_debit: number;
  sum_credit: number;
}

export interface GroupBalance {
  txn_group_id: string;
  sum_debit: number;
  sum_credit: number;
  balanced: boolean;
}

export interface LedgerFilters {
  posted_from?: string;
  posted_to?: string;
  account_code?: string;
  party_type?: string;
  party_id?: string;
  source_type?: string;
  source_id?: string;
  txn_group_id?: string;
  side?: 'DEBIT' | 'CREDIT';
  limit?: number;
  offset?: number;
}

export const ledgerService = {
  async query(filters: LedgerFilters = {}): Promise<LedgerPage> {
    const res = await api.get<LedgerPage>('/api/super-admin/ledger', {
      params: _cleanParams(filters as Record<string, unknown>),
    });
    return res.data;
  },
  async exportCsv(filters: Omit<LedgerFilters, 'limit' | 'offset'> = {}): Promise<Blob> {
    const res = await api.get('/api/super-admin/ledger/export.csv', {
      params: _cleanParams(filters as Record<string, unknown>),
      responseType: 'blob',
    });
    return res.data as Blob;
  },
  async groupBalance(txnGroupId: string): Promise<GroupBalance> {
    const res = await api.get<GroupBalance>(
      `/api/super-admin/ledger/groups/${encodeURIComponent(txnGroupId)}`,
    );
    return res.data;
  },
};

function _cleanParams(o: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(o)) {
    if (v !== undefined && v !== null && v !== '') out[k] = v;
  }
  return out;
}
