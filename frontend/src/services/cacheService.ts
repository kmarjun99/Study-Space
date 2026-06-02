/**
 * Cache Service - Super Admin cache management
 */
import api from './api';

export interface CacheScope {
    id: string;
    name: string;
    description: string;
}

export interface CacheClearResult {
    success: boolean;
    message: string;
    scopes_cleared: string[];
    keys_cleared: number;
    audit_id: string;
}

export const cacheService = {
    /**
     * Get available cache scopes
     */
    async getScopes(): Promise<CacheScope[]> {
        const response = await api.get('/admin/cache/scopes');
        return response.data.scopes || [];
    },

    /**
     * Clear specified cache scopes
     */
    async clearCache(scopes: string[]): Promise<CacheClearResult> {
        const response = await api.post('/admin/cache/clear', { scope: scopes });
        return response.data;
    }
};
