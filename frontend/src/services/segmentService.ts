/**
 * Segment management — super-admin CRUD + member list + recompute trigger.
 * Plus a transparency call for the student page.
 */
import api from './api';

export type SegmentRuleType =
  | 'HIGH_INTENT'
  | 'BUDGET_BAND'
  | 'CITY_INTEREST'
  | 'AMENITY_INTEREST'
  | 'PAYMENT_ABANDONED'
  | 'REPEAT_SEARCH_NO_BOOKING'
  | 'CANCELLED_USERS';

export interface Segment {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  rule_type: SegmentRuleType;
  rule_config: Record<string, unknown>;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface SegmentMember {
  user_id: string;
  score: number;
  reason: string | null;
  entered_at: string;
  is_active: boolean;
}

export interface MySegment {
  segment_slug: string;
  segment_name: string;
  rule_type: SegmentRuleType;
  score: number;
  reason: string | null;
  entered_at: string;
}

export interface SegmentInput {
  slug: string;
  name: string;
  description?: string;
  rule_type: SegmentRuleType;
  rule_config: Record<string, unknown>;
}

export interface SegmentPatch {
  name?: string;
  description?: string;
  rule_config?: Record<string, unknown>;
  is_active?: boolean;
}

export const segmentService = {
  // Super-admin
  async list(includeInactive = false): Promise<Segment[]> {
    const res = await api.get<Segment[]>('/api/super-admin/segments', {
      params: { include_inactive: includeInactive },
    });
    return res.data;
  },
  async create(input: SegmentInput): Promise<Segment> {
    const res = await api.post<Segment>('/api/super-admin/segments', input);
    return res.data;
  },
  async patch(id: string, body: SegmentPatch): Promise<Segment> {
    const res = await api.patch<Segment>(`/api/super-admin/segments/${id}`, body);
    return res.data;
  },
  async softDelete(id: string): Promise<Segment> {
    const res = await api.delete<Segment>(`/api/super-admin/segments/${id}`);
    return res.data;
  },
  async members(id: string, limit = 200, offset = 0): Promise<SegmentMember[]> {
    const res = await api.get<SegmentMember[]>(
      `/api/super-admin/segments/${id}/members`,
      { params: { limit, offset } },
    );
    return res.data;
  },
  async recompute(): Promise<{
    segments_evaluated: number;
    memberships_entered: number;
    memberships_exited: number;
    skipped: string[];
  }> {
    const res = await api.post('/api/super-admin/segments/recompute');
    return res.data;
  },
  // Student transparency
  async listMine(): Promise<MySegment[]> {
    const res = await api.get<MySegment[]>('/api/users/me/segments');
    return res.data;
  },
};
