import React, { useState, useCallback } from 'react';
import { GoogleMap, LoadScript, Marker } from '@react-google-maps/api';
import { MapPin, Crosshair, Check } from 'lucide-react';
import { geocodingService } from '../services/geocoding';
import toast from 'react-hot-toast';

interface MapVenueSelectorProps {
    initialLocation?: { lat: number; lng: number };
    onLocationSelected: (location: {
        lat: number;
        lng: number;
        address: string;
        city?: string;
    }) => void;
    height?: string;
    className?: string;
}

const containerStyle = {
    width: '100%',
    height: '100%',
};

const defaultCenter = {
    lat: 28.6139, // Delhi default
    lng: 77.2090,
};

const MapVenueSelector: React.FC<MapVenueSelectorProps> = ({
    initialLocation,
    onLocationSelected,
    height = '500px',
    className = '',
}) => {
    const [markerPosition, setMarkerPosition] = useState<{ lat: number; lng: number } | null>(
        initialLocation || null
    );
    const [mapCenter, setMapCenter] = useState(initialLocation || defaultCenter);
    const [selectedAddress, setSelectedAddress] = useState<string>('');
    const [isLoadingAddress, setIsLoadingAddress] = useState(false);

    const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

    const handleMapClick = useCallback(
        async (event: google.maps.MapMouseEvent) => {
            if (event.latLng) {
                const lat = event.latLng.lat();
                const lng = event.latLng.lng();

                setMarkerPosition({ lat, lng });
                setIsLoadingAddress(true);

                // Reverse geocode to get address
                const result = await geocodingService.reverseGeocode(lat, lng);

                setIsLoadingAddress(false);

                if (result) {
                    setSelectedAddress(result.address);
                    toast.success('Location selected!');
                } else {
                    setSelectedAddress(`${lat.toFixed(6)}, ${lng.toFixed(6)}`);
                    toast.error('Could not fetch address for this location');
                }
            }
        },
        []
    );

    const handleUseMyLocation = async () => {
        const location = await geocodingService.getCurrentLocation();

        if (location) {
            setMarkerPosition(location);
            setMapCenter(location);
            setIsLoadingAddress(true);

            const result = await geocodingService.reverseGeocode(location.lat, location.lng);
            setIsLoadingAddress(false);

            if (result) {
                setSelectedAddress(result.address);
                toast.success('Using your current location');
            }
        } else {
            toast.error('Could not get your location');
        }
    };

    const handleConfirmLocation = () => {
        if (markerPosition) {
            onLocationSelected({
                lat: markerPosition.lat,
                lng: markerPosition.lng,
                address: selectedAddress,
                city: selectedAddress.split(',')[0]?.trim(), // Extract city from address
            });
            toast.success('Location confirmed!');
        } else {
            toast.error('Please select a location on the map');
        }
    };

    if (!apiKey) {
        return (
            <div
                className={`bg-gray-100 rounded-xl flex items-center justify-center ${className}`}
                style={{ height }}
            >
                <div className="text-center p-6">
                    <MapPin className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600 font-medium">Google Maps API key not configured</p>
                    <p className="text-gray-500 text-sm mt-2">
                        Add VITE_GOOGLE_MAPS_API_KEY to your .env file
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className={className}>
            <div className="bg-white rounded-xl shadow-lg overflow-hidden">
                {/* Instructions */}
                <div className="p-4 bg-indigo-50 border-b border-indigo-100">
                    <p className="text-sm text-indigo-700 flex items-center gap-2">
                        <MapPin className="w-4 h-4" />
                        Click anywhere on the map to select your venue location
                    </p>
                </div>

                {/* Map Container */}
                <div style={{ height }} className="relative">
                    <LoadScript googleMapsApiKey={apiKey}>
                        <GoogleMap
                            mapContainerStyle={containerStyle}
                            center={mapCenter}
                            zoom={13}
                            onClick={handleMapClick}
                            options={{
                                zoomControl: true,
                                streetViewControl: true,
                                mapTypeControl: true,
                                fullscreenControl: true,
                            }}
                        >
                            {markerPosition && (
                                <Marker
                                    position={markerPosition}
                                    icon={{
                                        path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z',
                                        fillColor: '#6366f1',
                                        fillOpacity: 1,
                                        strokeColor: '#ffffff',
                                        strokeWeight: 2,
                                        scale: 2,
                                        anchor: new google.maps.Point(12, 22),
                                    }}
                                    animation={google.maps.Animation.DROP}
                                />
                            )}
                        </GoogleMap>
                    </LoadScript>

                    {/* Use My Location Button */}
                    <button
                        onClick={handleUseMyLocation}
                        className="absolute top-4 right-4 bg-white rounded-lg shadow-lg p-3 hover:bg-gray-50 transition-colors"
                        title="Use my current location"
                    >
                        <Crosshair className="w-5 h-5 text-indigo-600" />
                    </button>
                </div>

                {/* Selected Location Info */}
                {markerPosition && (
                    <div className="p-4 bg-white border-t border-gray-200">
                        <div className="flex items-start gap-3">
                            <MapPin className="w-5 h-5 text-indigo-600 mt-0.5 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 mb-1">
                                    Selected Location
                                </p>
                                {isLoadingAddress ? (
                                    <p className="text-sm text-gray-500">Fetching address...</p>
                                ) : (
                                    <>
                                        <p className="text-sm text-gray-600 mb-2">{selectedAddress}</p>
                                        <p className="text-xs text-gray-500">
                                            Coordinates: {markerPosition.lat.toFixed(6)}, {markerPosition.lng.toFixed(6)}
                                        </p>
                                    </>
                                )}
                            </div>
                            <button
                                onClick={handleConfirmLocation}
                                disabled={isLoadingAddress}
                                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
                            >
                                <Check className="w-4 h-4" />
                                Confirm
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default MapVenueSelector;
