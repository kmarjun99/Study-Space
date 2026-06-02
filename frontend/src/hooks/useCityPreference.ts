/**
 * City Preference Hook - Persists user's preferred city in localStorage
 * Used to remember city selection across pages and sessions
 */
import { useState, useEffect, useCallback } from 'react';
import { LocationResult } from '../components/LocationSearch';

const CITY_PREFERENCE_KEY = 'sspace_city_preference';

export interface CityPreference {
    location: LocationResult | null;
    displayName: string;
}

export const useCityPreference = () => {
    const [preference, setPreference] = useState<CityPreference>({
        location: null,
        displayName: ''
    });

    // Load from localStorage on mount
    useEffect(() => {
        try {
            const stored = localStorage.getItem(CITY_PREFERENCE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                setPreference(parsed);
            }
        } catch (e) {
            console.warn('Failed to load city preference:', e);
        }
    }, []);

    // Set city preference
    const setCityPreference = useCallback((location: LocationResult | null) => {
        const newPref: CityPreference = {
            location,
            displayName: location?.display_name || ''
        };
        setPreference(newPref);

        try {
            if (location) {
                localStorage.setItem(CITY_PREFERENCE_KEY, JSON.stringify(newPref));
            } else {
                localStorage.removeItem(CITY_PREFERENCE_KEY);
            }
        } catch (e) {
            console.warn('Failed to save city preference:', e);
        }
    }, []);

    // Clear city preference
    const clearCityPreference = useCallback(() => {
        setPreference({ location: null, displayName: '' });
        try {
            localStorage.removeItem(CITY_PREFERENCE_KEY);
        } catch (e) {
            console.warn('Failed to clear city preference:', e);
        }
    }, []);

    return {
        cityPreference: preference.location,
        cityDisplayName: preference.displayName,
        setCityPreference,
        clearCityPreference,
        hasCityPreference: !!preference.location
    };
};

export default useCityPreference;
