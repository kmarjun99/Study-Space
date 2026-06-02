/**
 * LocationSelector - Cascading location dropdowns for State > City > Locality
 * Used in venue and accommodation onboarding forms
 */
import React, { useState, useEffect } from 'react';
import { locationService, LocationSearchResult } from '../services/locationService';
import { ChevronDown, MapPin, Loader2 } from 'lucide-react';

export interface LocationData {
    state: string;
    city: string;
    locality?: string;
    locationId?: string;
    pincode?: string;
    address?: string;
    latitude?: number;
    longitude?: number;
}

interface LocationSelectorProps {
    value: LocationData;
    onChange: (data: LocationData) => void;
    disabled?: boolean;
    showPincode?: boolean;
    showAddress?: boolean;
    showCoordinates?: boolean;
    required?: boolean;
}

export const LocationSelector: React.FC<LocationSelectorProps> = ({
    value,
    onChange,
    disabled = false,
    showPincode = true,
    showAddress = true,
    showCoordinates = false,
    required = true
}) => {
    // States list
    const [states, setStates] = useState<string[]>([]);
    const [loadingStates, setLoadingStates] = useState(true);

    // Cities list (filtered by state)
    const [cities, setCities] = useState<string[]>([]);
    const [loadingCities, setLoadingCities] = useState(false);

    // Localities list (filtered by city)
    const [localities, setLocalities] = useState<LocationSearchResult[]>([]);
    const [loadingLocalities, setLoadingLocalities] = useState(false);

    // Load states on mount
    useEffect(() => {
        const loadStates = async () => {
            setLoadingStates(true);
            try {
                const data = await locationService.getStates();
                setStates(Array.isArray(data) ? data : []);
            } catch (e) {
                console.error("Failed to load states", e);
                setStates([]);
            } finally {
                setLoadingStates(false);
            }
        };
        loadStates();
    }, []);

    // Load cities when state changes
    useEffect(() => {
        if (!value.state) {
            setCities([]);
            return;
        }

        const loadCities = async () => {
            setLoadingCities(true);
            try {
                const data = await locationService.getCitiesByState(value.state);
                setCities(Array.isArray(data) ? data : []);
            } catch (e) {
                console.error("Failed to load cities", e);
                setCities([]);
            } finally {
                setLoadingCities(false);
            }
        };
        loadCities();
    }, [value.state]);

    // Load localities when city changes
    useEffect(() => {
        if (!value.state || !value.city) {
            setLocalities([]);
            return;
        }

        const loadLocalities = async () => {
            setLoadingLocalities(true);
            try {
                const data = await locationService.getLocalitiesByCity(value.state, value.city);
                setLocalities(Array.isArray(data) ? data : []);
            } catch (e) {
                console.error("Failed to load localities", e);
                setLocalities([]);
            } finally {
                setLoadingLocalities(false);
            }
        };
        loadLocalities();
    }, [value.state, value.city]);

    const handleStateChange = (newState: string) => {
        onChange({
            ...value,
            state: newState,
            city: '',
            locality: '',
            locationId: undefined
        });
    };

    const handleCityChange = (newCity: string) => {
        onChange({
            ...value,
            city: newCity,
            locality: '',
            locationId: undefined
        });
    };

    const handleLocalityChange = (localityId: string) => {
        const selected = localities.find(l => l.id === localityId);
        if (selected) {
            onChange({
                ...value,
                locality: selected.locality || '',
                locationId: selected.id
            });
            // Track usage for popularity
            locationService.trackUsage(selected.id);
        }
    };

    const validatePincode = (pincode: string): boolean => {
        return /^\d{6}$/.test(pincode);
    };

    const selectClass = `
        w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 
        transition-all duration-200 appearance-none bg-white
        ${disabled ? 'bg-gray-100 cursor-not-allowed' : 'hover:border-gray-400'}
    `;

    const labelClass = "block text-sm font-medium text-gray-700 mb-1";

    return (
        <div className="space-y-4">
            {/* State & City Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* State Dropdown */}
                <div>
                    <label className={labelClass}>
                        State {required && <span className="text-red-500">*</span>}
                    </label>
                    <div className="relative">
                        <select
                            value={value.state || ''}
                            onChange={(e) => handleStateChange(e.target.value)}
                            disabled={disabled || loadingStates}
                            className={selectClass}
                            required={required}
                        >
                            <option value="">
                                {loadingStates ? 'Loading states...' : 'Select State'}
                            </option>
                            {Array.isArray(states) && states.map(state => (
                                <option key={state} value={state}>{state}</option>
                            ))}
                        </select>
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                            {loadingStates ? (
                                <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                            ) : (
                                <ChevronDown className="w-4 h-4 text-gray-400" />
                            )}
                        </div>
                    </div>
                </div>

                {/* City Dropdown */}
                <div>
                    <label className={labelClass}>
                        City {required && <span className="text-red-500">*</span>}
                    </label>
                    <div className="relative">
                        <select
                            value={value.city || ''}
                            onChange={(e) => handleCityChange(e.target.value)}
                            disabled={disabled || !value.state || loadingCities}
                            className={selectClass}
                            required={required}
                        >
                            <option value="">
                                {!value.state ? 'Select state first' : loadingCities ? 'Loading cities...' : 'Select City'}
                            </option>
                            {Array.isArray(cities) && cities.map(city => (
                                <option key={city} value={city}>{city}</option>
                            ))}
                        </select>
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                            {loadingCities ? (
                                <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                            ) : (
                                <ChevronDown className="w-4 h-4 text-gray-400" />
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Locality & Pincode Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Locality Dropdown */}
                <div>
                    <label className={labelClass}>
                        Locality / Area
                        <span className="text-gray-400 text-xs ml-1">(Recommended)</span>
                    </label>
                    <div className="relative">
                        <select
                            value={value.locationId || ''}
                            onChange={(e) => handleLocalityChange(e.target.value)}
                            disabled={disabled || !value.city || loadingLocalities}
                            className={selectClass}
                        >
                            <option value="">
                                {!value.city ? 'Select city first' : loadingLocalities ? 'Loading localities...' : 'Select Locality'}
                            </option>
                            {Array.isArray(localities) && localities.map(loc => (
                                <option key={loc.id} value={loc.id}>
                                    {loc.locality || loc.display_name}
                                </option>
                            ))}
                        </select>
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                            {loadingLocalities ? (
                                <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                            ) : (
                                <ChevronDown className="w-4 h-4 text-gray-400" />
                            )}
                        </div>
                    </div>
                </div>

                {/* Pincode */}
                {showPincode && (
                    <div>
                        <label className={labelClass}>
                            Pincode {required && <span className="text-red-500">*</span>}
                        </label>
                        <input
                            type="text"
                            value={value.pincode || ''}
                            onChange={(e) => {
                                const val = e.target.value.replace(/\D/g, '').slice(0, 6);
                                onChange({ ...value, pincode: val });
                            }}
                            placeholder="6-digit pincode"
                            disabled={disabled}
                            maxLength={6}
                            pattern="\d{6}"
                            required={required}
                            className={`${selectClass} ${value.pincode && !validatePincode(value.pincode)
                                ? 'border-red-300 focus:ring-red-500'
                                : ''
                                }`}
                        />
                        {value.pincode && !validatePincode(value.pincode) && (
                            <p className="text-xs text-red-500 mt-1">Pincode must be 6 digits</p>
                        )}
                    </div>
                )}
            </div>

            {/* Full Address */}
            {showAddress && (
                <div>
                    <label className={labelClass}>
                        Full Address {required && <span className="text-red-500">*</span>}
                    </label>
                    <textarea
                        value={value.address || ''}
                        onChange={(e) => onChange({ ...value, address: e.target.value })}
                        placeholder="Building name, street, landmark..."
                        disabled={disabled}
                        required={required}
                        rows={2}
                        className={`${selectClass} resize-none`}
                    />
                </div>
            )}

            {/* Coordinates (Optional) */}
            {showCoordinates && (
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className={labelClass}>
                            Latitude <span className="text-gray-400 text-xs">(Optional)</span>
                        </label>
                        <input
                            type="number"
                            step="any"
                            value={value.latitude || ''}
                            onChange={(e) => onChange({ ...value, latitude: parseFloat(e.target.value) || undefined })}
                            placeholder="e.g. 12.9716"
                            disabled={disabled}
                            className={selectClass}
                        />
                    </div>
                    <div>
                        <label className={labelClass}>
                            Longitude <span className="text-gray-400 text-xs">(Optional)</span>
                        </label>
                        <input
                            type="number"
                            step="any"
                            value={value.longitude || ''}
                            onChange={(e) => onChange({ ...value, longitude: parseFloat(e.target.value) || undefined })}
                            placeholder="e.g. 77.5946"
                            disabled={disabled}
                            className={selectClass}
                        />
                    </div>
                </div>
            )}

            {/* Selected Location Display */}
            {value.state && value.city && (
                <div className="flex items-center gap-2 text-sm text-gray-600 bg-gray-50 p-2 rounded-lg">
                    <MapPin className="w-4 h-4 text-indigo-500" />
                    <span>
                        {[value.locality, value.city, value.state].filter(Boolean).join(', ')}
                        {value.pincode && ` - ${value.pincode}`}
                    </span>
                </div>
            )}
        </div>
    );
};

export default LocationSelector;
