/**
 * Geocoding Service for Google Maps
 * Converts addresses to coordinates and vice versa
 */

interface GeocodeResult {
    lat: number;
    lng: number;
    address: string;
    city?: string;
    state?: string;
    country?: string;
    postalCode?: string;
}

class GeocodingService {
    private apiKey: string;

    constructor() {
        this.apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '';
    }

    /**
     * Convert address string to coordinates
     */
    async geocodeAddress(address: string): Promise<GeocodeResult | null> {
        if (!this.apiKey) {
            console.error('Google Maps API key is not configured');
            return null;
        }

        try {
            const response = await fetch(
                `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(address)}&key=${this.apiKey}`
            );

            const data = await response.json();

            if (data.status === 'OK' && data.results.length > 0) {
                const result = data.results[0];
                const location = result.geometry.location;

                // Extract address components
                let city = '';
                let state = '';
                let country = '';
                let postalCode = '';

                result.address_components?.forEach((component: any) => {
                    const types = component.types;
                    if (types.includes('locality')) {
                        city = component.long_name;
                    } else if (types.includes('administrative_area_level_1')) {
                        state = component.long_name;
                    } else if (types.includes('country')) {
                        country = component.long_name;
                    } else if (types.includes('postal_code')) {
                        postalCode = component.long_name;
                    }
                });

                return {
                    lat: location.lat,
                    lng: location.lng,
                    address: result.formatted_address,
                    city,
                    state,
                    country,
                    postalCode,
                };
            }

            console.error('Geocoding failed:', data.status);
            return null;
        } catch (error) {
            console.error('Error geocoding address:', error);
            return null;
        }
    }

    /**
     * Convert coordinates to address (Reverse Geocoding)
     */
    async reverseGeocode(lat: number, lng: number): Promise<GeocodeResult | null> {
        if (!this.apiKey) {
            console.error('Google Maps API key is not configured');
            return null;
        }

        try {
            const response = await fetch(
                `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${this.apiKey}`
            );

            const data = await response.json();

            if (data.status === 'OK' && data.results.length > 0) {
                const result = data.results[0];

                // Extract address components
                let city = '';
                let state = '';
                let country = '';
                let postalCode = '';

                result.address_components?.forEach((component: any) => {
                    const types = component.types;
                    if (types.includes('locality')) {
                        city = component.long_name;
                    } else if (types.includes('administrative_area_level_1')) {
                        state = component.long_name;
                    } else if (types.includes('country')) {
                        country = component.long_name;
                    } else if (types.includes('postal_code')) {
                        postalCode = component.long_name;
                    }
                });

                return {
                    lat,
                    lng,
                    address: result.formatted_address,
                    city,
                    state,
                    country,
                    postalCode,
                };
            }

            console.error('Reverse geocoding failed:', data.status);
            return null;
        } catch (error) {
            console.error('Error reverse geocoding:', error);
            return null;
        }
    }

    /**
     * Calculate distance between two points using Haversine formula
     */
    calculateDistance(
        lat1: number,
        lng1: number,
        lat2: number,
        lng2: number
    ): number {
        const R = 6371; // Earth's radius in kilometers
        const dLat = this.toRad(lat2 - lat1);
        const dLng = this.toRad(lng2 - lng1);

        const a =
            Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(this.toRad(lat1)) *
                Math.cos(this.toRad(lat2)) *
                Math.sin(dLng / 2) *
                Math.sin(dLng / 2);

        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        const distance = R * c;

        return Math.round(distance * 100) / 100; // Round to 2 decimal places
    }

    private toRad(degrees: number): number {
        return degrees * (Math.PI / 180);
    }

    /**
     * Get user's current location
     */
    getCurrentLocation(): Promise<{ lat: number; lng: number } | null> {
        return new Promise((resolve) => {
            if (!navigator.geolocation) {
                console.error('Geolocation is not supported by this browser');
                resolve(null);
                return;
            }

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    resolve({
                        lat: position.coords.latitude,
                        lng: position.coords.longitude,
                    });
                },
                (error) => {
                    console.error('Error getting location:', error);
                    resolve(null);
                }
            );
        });
    }
}

// Export singleton instance
export const geocodingService = new GeocodingService();
export default geocodingService;
