import React, { useState } from 'react';
import { GoogleMap, LoadScript, Marker, InfoWindow } from '@react-google-maps/api';
import { MapPin } from 'lucide-react';

interface MapLocation {
    id?: string | number;
    lat: number;
    lng: number;
    title?: string;
    address?: string;
}

interface MapProps {
    center: { lat: number; lng: number };
    zoom?: number;
    markers?: MapLocation[];
    onMarkerClick?: (marker: MapLocation) => void;
    height?: string;
    className?: string;
    showInfoWindow?: boolean;
}

const containerStyle = {
    width: '100%',
    height: '100%',
};

const defaultCenter = {
    lat: 28.6139, // Delhi default
    lng: 77.2090,
};

const Map: React.FC<MapProps> = ({
    center = defaultCenter,
    zoom = 13,
    markers = [],
    onMarkerClick,
    height = '400px',
    className = '',
    showInfoWindow = true,
}) => {
    const [selectedMarker, setSelectedMarker] = useState<MapLocation | null>(null);
    const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

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

    const handleMarkerClick = (marker: MapLocation) => {
        setSelectedMarker(marker);
        if (onMarkerClick) {
            onMarkerClick(marker);
        }
    };

    return (
        <div className={className} style={{ height }}>
            <LoadScript googleMapsApiKey={apiKey}>
                <GoogleMap
                    mapContainerStyle={containerStyle}
                    center={center}
                    zoom={zoom}
                    options={{
                        zoomControl: true,
                        streetViewControl: false,
                        mapTypeControl: false,
                        fullscreenControl: true,
                    }}
                >
                    {markers.map((marker, index) => (
                        <Marker
                            key={marker.id || index}
                            position={{ lat: marker.lat, lng: marker.lng }}
                            onClick={() => handleMarkerClick(marker)}
                            icon={{
                                path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z',
                                fillColor: '#6366f1',
                                fillOpacity: 1,
                                strokeColor: '#ffffff',
                                strokeWeight: 2,
                                scale: 1.5,
                                anchor: new google.maps.Point(12, 22),
                            }}
                        />
                    ))}

                    {showInfoWindow && selectedMarker && (
                        <InfoWindow
                            position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }}
                            onCloseClick={() => setSelectedMarker(null)}
                        >
                            <div className="p-2">
                                <h3 className="font-bold text-gray-900 mb-1">
                                    {selectedMarker.title || 'Location'}
                                </h3>
                                {selectedMarker.address && (
                                    <p className="text-sm text-gray-600">{selectedMarker.address}</p>
                                )}
                            </div>
                        </InfoWindow>
                    )}
                </GoogleMap>
            </LoadScript>
        </div>
    );
};

export default Map;
