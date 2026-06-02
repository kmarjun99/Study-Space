/**
 * Settlement Service.
 * Settlement-run endpoints — owner sees own runs; super-admin sees all + can
 * trigger the daily aggregator and record payout UTRs.
 */
import api from './api';

export type SettlementStatus =
  | 'DRAFT'
  | 'READY'
  | 'PAID'
  | 'FAILED'
  | 'NEGATIVE_HELD';

export interface SettlementRun {
  id: string;
  owner_id: string;
  period_start: string;
  period_end: string;
  gross: number;
  refunds: number;
  platform_offset: number;
  tcs_total: number;
  tds_total: number;
  net_payout: number;
  status: SettlementStatus;
  payout_ref: string | null;
  payout_at: string | null;
  failure_reason: string | null;
  created_at: string;
}

export type SettlementLineKind =
  | 'BOOKING'
  | 'REFUND'
  | 'TCS_CGST'
  | 'TCS_SGST'
  | 'TCS_IGST'
  | 'TDS_194O'
  | 'MAINTENANCE_OFFSET'
  | 'ADJUSTMENT';

export interface SettlementLine {
  id: string;
  kind: SettlementLineKind;
  reference_type: string | null;
  reference_id: string | null;
  base_amount: number;
  deduction: number;
  net: number;
  narration: string | null;
}

export interface SettlementDetail {
  run: SettlementRun;
  lines: SettlementLine[];
}

export const settlementService = {
  async listMyRuns(): Promise<SettlementRun[]> {
    const res = await api.get<SettlementRun[]>('/api/owner/settlements');
    return res.data;
  },
  async getMyRun(runId: string): Promise<SettlementDetail> {
    const res = await api.get<SettlementDetail>(`/api/owner/settlements/${runId}`);
    return res.data;
  },
  async listAllRuns(status?: SettlementStatus): Promise<SettlementRun[]> {
    const res = await api.get<SettlementRun[]>('/api/admin/settlements', {
      params: status ? { status } : undefined,
    });
    return res.data;
  },
  async triggerRun(nowIso?: string): Promise<{ runs_created: number; owners: number }> {
    const res = await api.post('/api/admin/settlements/run', { now: nowIso ?? null });
    return res.data;
  },
  async markPaid(runId: string, payoutRef: string): Promise<SettlementRun> {
    const res = await api.post<SettlementRun>(`/api/admin/settlements/${runId}/mark-paid`, {
      payout_ref: payoutRef,
    });
    return res.data;
  },
  async markFailed(runId: string, reason: string): Promise<SettlementRun> {
    const res = await api.post<SettlementRun>(`/api/admin/settlements/${runId}/mark-failed`, {
      reason,
    });
    return res.data;
  },
};
