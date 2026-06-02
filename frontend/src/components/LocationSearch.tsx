/**
 * LocationSearch Component - Autocomplete search for cities and localities
 * Fetches suggestions from /locations/autocomplete API after 2 characters
 */
import React, { useState, useEffect, useRef } from 'react';
import { MapPin, Search, X, Loader2 } from 'lucide-react';
import api from '../services/api';

export interface LocationResult {
    id: string;
    display_name: string;
    city: string;
    state: string;
    locality?: string;
}

interface LocationSearchProps {
    value?: string;
    placeholder?: string;
    onSelect: (location: LocationResult) => void;
    onClear?: () => void;
    className?: string;
    disabled?: boolean;
}

export const LocationSearch: React.FC<LocationSearchProps> = ({
    value = '',
    placeholder = 'Search city or locality...',
    onSelect,
    onClear,
    className = '',
    disabled = false
}) => {
    const [query, setQuery] = useState(value);
    const [suggestions, setSuggestions] = useState<LocationResult[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isOpen, setIsOpen] = useState(false);
    const [error, setError] = useState('');
    const wrapperRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Sync external value changes
    useEffect(() => {
        setQuery(value);
    }, [value]);

    // Debounced search
    useEffect(() => {
        const trimmedQuery = query.trim();

        // Only search after 2 characters
        if (trimmedQuery.length < 2) {
            setSuggestions([]);
            setIsOpen(false);
            return;
        }

        const timeoutId = setTimeout(async () => {
            setIsLoading(true);
            setError('');

            try {
                const response = await api.get('/locations/autocomplete', {
                    params: { q: trimmedQuery, limit: 10 }
                });
                setSuggestions(response.data);
                setIsOpen(response.data.length > 0);
            } catch (err) {
                console.error('Location search error:', err);
                setError('Unable to fetch locations');
                setSuggestions([]);
            } finally {
                setIsLoading(false);
            }
        }, 300); // 300ms debounce

        return () => clearTimeout(timeoutId);
    }, [query]);

    const handleSelect = (location: LocationResult) => {
        setQuery(location.display_name);
        setSuggestions([]);
        setIsOpen(false);
        onSelect(location);

        // Increment usage count (fire and forget)
        api.put(`/locations/${location.id}/increment-usage`).catch(() => { });
    };

    const handleClear = () => {
        setQuery('');
        setSuggestions([]);
        setIsOpen(false);
        onClear?.();
        inputRef.current?.focus();
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setQuery(e.target.value);
    };

    const handleFocus = () => {
        if (suggestions.length > 0) {
            setIsOpen(true);
        }
    };

    return (
        <div ref={wrapperRef} className={`relative ${className}`}>
            {/* Input Field */}
            <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    {isLoading ? (
                        <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />
                    ) : (
                        <Search className="h-4 w-4 text-gray-400" />
                    )}
                </div>

                <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={handleInputChange}
                    onFocus={handleFocus}
                    placeholder={placeholder}
                    disabled={disabled}
                    className={`
            w-full pl-10 pr-10 py-2.5 
            border border-gray-300 rounded-lg
            bg-white text-gray-900 text-sm
            placeholder:text-gray-400
            focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
            disabled:bg-gray-100 disabled:cursor-not-allowed
            transition-all duration-200
          `}
                />

                {query && !disabled && (
                    <button
                        type="button"
                        onClick={handleClear}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                    >
                        <X className="h-4 w-4" />
                    </button>
                )}
            </div>

            {/* Helper text */}
            {query.length > 0 && query.length < 2 && (
                <p className="mt-1 text-xs text-gray-500">Type at least 2 characters to search</p>
            )}

            {/* Error message */}
            {error && (
                <p className="mt-1 text-xs text-red-500">{error}</p>
            )}

            {/* Dropdown Suggestions */}
            {isOpen && suggestions.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {suggestions.map((location, index) => (
                        <button
                            key={location.id}
                            type="button"
                            onClick={() => handleSelect(location)}
                            className={`
                w-full px-4 py-3 text-left flex items-start gap-3
                hover:bg-indigo-50 transition-colors
                ${index !== suggestions.length - 1 ? 'border-b border-gray-100' : ''}
              `}
                        >
                            <MapPin className="h-4 w-4 text-indigo-500 mt-0.5 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">
                                    {location.display_name}
                                </p>
                                <p className="text-xs text-gray-500">
                                    {location.locality ? `${location.city}, ${location.state}` : location.state}
                                </p>
                            </div>
                        </button>
                    ))}
                </div>
            )}

            {/* No results */}
            {isOpen && query.length >= 2 && suggestions.length === 0 && !isLoading && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-4">
                    <p className="text-sm text-gray-500 text-center">
                        No locations found for "{query}"
                    </p>
                </div>
            )}
        </div>
    );
};

export default LocationSearch;
