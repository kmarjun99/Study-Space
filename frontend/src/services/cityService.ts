import api from './api';
import { CityStats, CityDetail } from '../types';

export const cityService = {
    getAllCities: async (): Promise<CityStats[]> => {
        const response = await api.get('/admin/cities/');
        return response.data;
    },

    getCityDetails: async (cityName: string): Promise<CityDetail> => {
        const response = await api.get(`/admin/cities/${encodeURIComponent(cityName)}`);
        return response.data;
    },

    updateCityStatus: async (cityName: string, isActive: boolean): Promise<CityStats> => {
        const response = await api.put(`/admin/cities/${encodeURIComponent(cityName)}/status`, {
            is_active: isActive
        });
        return response.data;
    }
};
