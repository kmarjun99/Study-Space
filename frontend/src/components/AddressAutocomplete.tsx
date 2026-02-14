import React, { useRef, useEffect, useState } from 'react';
import { LoadScript, Autocomplete } from '@react-google-maps/api';
import { MapPin, Loader2 } from 'lucide-react';

interface AddressAutocompleteProps {
    onPlaceSelected: (place: {
        address: string;
        lat: number;
        lng: number;
        city?: string;
        state?: string;
        country?: string;
        postalCode?: string;
    }) => void;
    defaultValue?: string;
    placeholder?: string;
    className?: string;
}

const libraries: ('places')[] = ['places'];

const AddressAutocomplete: React.FC<AddressAutocompleteProps> = ({
    onPlaceSelected,
    defaultValue = '',
    placeholder = 'Search for an address...',
    className = '',
}) => {
    const [autocomplete, setAutocomplete] = useState<google.maps.places.Autocomplete | null>(null);
    const [inputValue, setInputValue] = useState(defaultValue);
    const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

    useEffect(() => {
        setInputValue(defaultValue);
    }, [defaultValue]);

    if (!apiKey) {
        return (
            <div className={`relative ${className}`}>
                <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                        type="text"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        placeholder={placeholder}
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                        disabled
                    />
                </div>
                <p className="text-xs text-red-600 mt-1">
                    Google Maps API key required for autocomplete
                </p>
            </div>
        );
    }

    const onLoad = (autocompleteInstance: google.maps.places.Autocomplete) => {
        setAutocomplete(autocompleteInstance);
    };

    const onPlaceChanged = () => {
        if (autocomplete) {
            const place = autocomplete.getPlace();

            if (!place.geometry || !place.geometry.location) {
                console.error('No geometry found for the selected place');
                return;
            }

            const lat = place.geometry.location.lat();
            const lng = place.geometry.location.lng();
            const address = place.formatted_address || '';

            // Extract address components
            let city = '';
            let state = '';
            let country = '';
            let postalCode = '';

            place.address_components?.forEach((component) => {
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

            setInputValue(address);
            onPlaceSelected({
                address,
                lat,
                lng,
                city,
                state,
                country,
                postalCode,
            });
        }
    };

    return (
        <div className={`relative ${className}`}>
            <LoadScript googleMapsApiKey={apiKey} libraries={libraries}>
                <Autocomplete
                    onLoad={onLoad}
                    onPlaceChanged={onPlaceChanged}
                    options={{
                        componentRestrictions: { country: 'in' }, // Restrict to India
                        fields: ['address_components', 'formatted_address', 'geometry', 'name'],
                    }}
                >
                    <div className="relative">
                        <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5 z-10" />
                        <input
                            type="text"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            placeholder={placeholder}
                            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                        />
                    </div>
                </Autocomplete>
            </LoadScript>
        </div>
    );
};

export default AddressAutocomplete;
