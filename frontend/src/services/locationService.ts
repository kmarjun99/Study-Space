/**
 * Location Service - API calls for location search and management
 */
import api from './api';
import { Location } from '../types';

export interface LocationSearchResult {
    id: string;
    display_name: string;
    city: string;
    state: string;
    locality?: string;
}

export interface LocationDetails extends Location {
    usage_count: number;
    is_active: boolean;
}

export const locationService = {
    /**
     * Autocomplete search for locations
     * @param query - Search query (min 2 characters)
     * @param limit - Max results to return (default 10)
     */
    autocomplete: async (query: string, limit = 10): Promise<LocationSearchResult[]> => {
        if (query.trim().length < 2) {
            return [];
        }

        try {
            const response = await api.get('/locations/autocomplete', {
                params: { q: query.trim(), limit }
            });
            // Defensive check: Ensure response.data is an array
            return Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error('Location autocomplete error:', error);
            return [];
        }
    },

    /**
     * Get all locations (optionally filtered)
     */
    getAll: async (filters?: { city?: string; state?: string }): Promise<LocationDetails[]> => {
        try {
            const response = await api.get('/locations/', { params: filters });
            const data = Array.isArray(response.data) ? response.data : [];
            return data.map((loc: any) => ({
                id: loc.id,
                country: loc.country,
                state: loc.state,
                city: loc.city,
                locality: loc.locality,
                displayName: loc.display_name,
                latitude: loc.latitude,
                longitude: loc.longitude,
                usage_count: loc.usage_count,
                is_active: loc.is_active
            }));
        } catch (error) {
            console.error('Get locations error:', error);
            return [];
        }
    },

    /**
     * Get a specific location by ID
     */
    getById: async (id: string): Promise<LocationDetails | null> => {
        try {
            const response = await api.get(`/locations/${id}`);
            const loc = response.data;
            if (!loc) return null;
            return {
                id: loc.id,
                country: loc.country,
                state: loc.state,
                city: loc.city,
                locality: loc.locality,
                displayName: loc.display_name,
                latitude: loc.latitude,
                longitude: loc.longitude,
                usage_count: loc.usage_count,
                is_active: loc.is_active
            };
        } catch (error) {
            console.error('Get location by ID error:', error);
            return null;
        }
    },

    /**
     * Track location usage (called when user selects a location)
     */
    trackUsage: async (locationId: string): Promise<void> => {
        try {
            await api.put(`/locations/${locationId}/increment-usage`);
        } catch (error) {
            // Silent fail - usage tracking is not critical
            console.warn('Failed to track location usage:', error);
        }
    },

    /**
     * Get all unique states for dropdown
     */
    getStates: async (): Promise<string[]> => {
        try {
            const response = await api.get('/locations/states');
            // Defensive check: Ensure response.data is an array
            return Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error('Get states error:', error);
            return [];
        }
    },

    /**
     * Get cities for a specific state
     */
    getCitiesByState: async (state: string): Promise<string[]> => {
        try {
            const response = await api.get('/locations/cities', { params: { state } });
            // Defensive check: Ensure response.data is an array
            return Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error('Get cities by state error:', error);
            return [];
        }
    },

    /**
     * Get localities for a specific state and city
     */
    getLocalitiesByCity: async (state: string, city: string): Promise<LocationSearchResult[]> => {
        try {
            const response = await api.get('/locations/localities', { params: { state, city } });
            // Defensive check: Ensure response.data is an array
            return Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error('Get localities error:', error);
            return [];
        }
    },

    /**
     * Get unique cities for dropdown (no autocomplete) - DEPRECATED, use getCitiesByState
     */
    getCities: async (): Promise<string[]> => {
        try {
            const response = await api.get('/locations/');
            const locations = Array.isArray(response.data) ? response.data : [];
            const cities = [...new Set(locations.map((loc: any) => loc.city as string))];
            return cities.sort();
        } catch (error) {
            console.error('Get cities error:', error);
            return [];
        }
    },

    // ============================================================
    // SUPER ADMIN FUNCTIONS
    // ============================================================

    /**
     * Create a new location (Super Admin only)
     */
    create: async (data: {
        state: string;
        city: string;
        locality?: string;
        latitude?: number;
        longitude?: number;
        country?: string;
    }): Promise<LocationDetails> => {
        const response = await api.post('/locations/', {
            country: data.country || 'India',
            state: data.state,
            city: data.city,
            locality: data.locality || null,
            latitude: data.latitude || null,
            longitude: data.longitude || null
        });
        const loc = response.data;
        return {
            id: loc.id,
            country: loc.country,
            state: loc.state,
            city: loc.city,
            locality: loc.locality,
            displayName: loc.display_name,
            latitude: loc.latitude,
            longitude: loc.longitude,
            usage_count: loc.usage_count,
            is_active: loc.is_active
        };
    },

    /**
     * Update a location (Super Admin only)
     */
    update: async (id: string, data: {
        state?: string;
        city?: string;
        locality?: string;
        latitude?: number;
        longitude?: number;
        is_active?: boolean;
    }): Promise<LocationDetails> => {
        const response = await api.put(`/locations/${id}`, data);
        const loc = response.data;
        return {
            id: loc.id,
            country: loc.country,
            state: loc.state,
            city: loc.city,
            locality: loc.locality,
            displayName: loc.display_name,
            latitude: loc.latitude,
            longitude: loc.longitude,
            usage_count: loc.usage_count,
            is_active: loc.is_active
        };
    },

    /**
     * Delete (deactivate) a location (Super Admin only)
     */
    delete: async (id: string): Promise<void> => {
        await api.delete(`/locations/${id}`);
    },

    /**
     * Get all locations including inactive (for admin view)
     */
    getAllAdmin: async (): Promise<LocationDetails[]> => {
        try {
            const response = await api.get('/locations/', { params: { active_only: false } });
            const data = Array.isArray(response.data) ? response.data : [];
            return data.map((loc: any) => ({
                id: loc.id,
                country: loc.country,
                state: loc.state,
                city: loc.city,
                locality: loc.locality,
                displayName: loc.display_name,
                latitude: loc.latitude,
                longitude: loc.longitude,
                usage_count: loc.usage_count,
                is_active: loc.is_active
            }));
        } catch (error) {
            console.error('Get all locations (admin) error:', error);
            return [];
        }
    }
};

export default locationService;
