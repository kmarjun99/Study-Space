/**
 * Tax Config Service (super-admin only writes).
 * The value field is intentionally `unknown` — backend stores arbitrary JSON.
 */
import api from './api';

export interface TaxConfigItem {
  key: string;
  value: unknown;
  description: string | null;
  updated_by: string | null;
  updated_at: string | null;
}

export const taxConfigService = {
  async list(): Promise<TaxConfigItem[]> {
    const res = await api.get<TaxConfigItem[]>('/api/admin/tax-config');
    return res.data;
  },

  async upsert(key: string, value: unknown, description?: string): Promise<TaxConfigItem> {
    const res = await api.put<TaxConfigItem>(
      `/api/admin/tax-config/${encodeURIComponent(key)}`,
      { value, description },
    );
    return res.data;
  },
};
