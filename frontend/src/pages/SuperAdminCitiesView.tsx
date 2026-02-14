
import React, { useState, useEffect } from 'react';
import { Card, Button, Badge } from '../components/UI';
import { MapPin, ExternalLink } from 'lucide-react';
import { cityService } from '../services/cityService';
import { Input } from '../components/UI'; // Assuming Input is in UI

// Interfaces (if not in a shared type file, otherwise import them)
interface CityStats {
    name: string;
    total_venues: number;
    total_cabins: number; // desks
    occupancy_rate: number;
    is_active: boolean;
}

interface CityDetail extends CityStats {
    total_accommodations: number;
    active_bookings: number;
    owners: any[];
    areas: {
        name: string;
        venue_count: number;
        cabin_count: number;
    }[];
}

export const SuperAdminCitiesView = () => {
    const [cities, setCities] = useState<CityStats[]>([]);
    const [selectedCity, setSelectedCity] = useState<CityDetail | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadCities();
    }, []);

    const loadCities = async () => {
        try {
            const data = await cityService.getAllCities();
            setCities(data);
        } catch (err) {
            console.error("Failed to load cities", err);
        } finally {
            setLoading(false);
        }
    };

    const handleViewCity = async (cityName: string) => {
        setLoading(true);
        try {
            const detail = await cityService.getCityDetails(cityName);
            setSelectedCity(detail);
        } catch (err) {
            console.error("Failed to load city details", err);
        } finally {
            setLoading(false);
        }
    };

    const handleToggleStatus = async (cityName: string, currentStatus: boolean, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm(`Are you sure you want to ${currentStatus ? 'disable' : 'enable'} ${cityName}?`)) return;
        try {
            await cityService.updateCityStatus(cityName, !currentStatus);
            loadCities(); // Refresh list
            if (selectedCity && selectedCity.name === cityName) {
                setSelectedCity(prev => prev ? { ...prev, is_active: !currentStatus } : null);
            }
        } catch (err) {
            alert("Failed to update status");
        }
    };

    if (selectedCity) {
        return (
            <div className="space-y-6 animate-in fade-in">
                <Button variant="ghost" onClick={() => setSelectedCity(null)} className="mb-4">
                    &larr; Back to Cities
                </Button>

                <div className="flex justify-between items-start">
                    <div>
                        <h2 className="text-3xl font-bold text-gray-900">{selectedCity.name}</h2>
                        <div className="flex items-center gap-2 mt-2">
                            <Badge variant={selectedCity.is_active ? 'success' : 'error'}>
                                {selectedCity.is_active ? 'Active Market' : 'Disabled'}
                            </Badge>
                            <span className="text-gray-500 text-sm">Last synced: Just now</span>
                        </div>
                    </div>
                    <Button
                        variant={selectedCity.is_active ? 'outline' : 'primary'}
                        onClick={(e) => handleToggleStatus(selectedCity.name, selectedCity.is_active, e)}
                    >
                        {selectedCity.is_active ? 'Disable City' : 'Enable City'}
                    </Button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <Card className="p-6">
                        <h4 className="text-sm font-medium text-gray-500 uppercase">Total Supply</h4>
                        <p className="text-3xl font-bold text-gray-900 mt-2">{selectedCity.total_venues}</p>
                        <div className="mt-2 text-xs flex gap-2">
                            <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded full">{selectedCity.total_accommodations} Beds</span>
                            <span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded full">{selectedCity.total_cabins} Desks</span>
                        </div>
                    </Card>
                    <Card className="p-6">
                        <h4 className="text-sm font-medium text-gray-500 uppercase">Active Demand</h4>
                        {/* Placeholder for real bookings */}
                        <p className="text-3xl font-bold text-gray-900 mt-2">{selectedCity.active_bookings}</p>
                        <p className="text-xs text-green-600 mt-1">↑ 5% this week</p>
                    </Card>
                    <Card className="p-6">
                        <h4 className="text-sm font-medium text-gray-500 uppercase">Occupancy</h4>
                        <p className="text-3xl font-bold text-gray-900 mt-2">{selectedCity.occupancy_rate}%</p>
                        <div className="w-full bg-gray-200 rounded-full h-1.5 mt-2">
                            <div className="bg-indigo-600 h-1.5 rounded-full" style={{ width: `${selectedCity.occupancy_rate}%` }}></div>
                        </div>
                    </Card>
                    <Card className="p-6">
                        <h4 className="text-sm font-medium text-gray-500 uppercase">Owners</h4>
                        <p className="text-3xl font-bold text-gray-900 mt-2">{selectedCity.owners.length}</p>
                        <p className="text-xs text-gray-400 mt-1">Active Partners</p>
                    </Card>
                </div>

                <Card className="p-0 overflow-hidden">
                    <div className="p-4 border-b border-gray-100 bg-gray-50">
                        <h3 className="font-bold text-gray-900">Area Breakdown</h3>
                    </div>
                    <table className="w-full text-left text-sm text-gray-500">
                        <thead className="bg-gray-50 text-xs uppercase text-gray-700">
                            <tr>
                                <th className="px-6 py-3">Area Name</th>
                                <th className="px-6 py-3">Venue Count</th>
                                <th className="px-6 py-3">Desk Capacity</th>
                                <th className="px-6 py-3">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {selectedCity.areas.map((area, idx) => (
                                <tr key={idx} className="hover:bg-gray-50">
                                    <td className="px-6 py-4 font-medium text-gray-900">{area.name}</td>
                                    <td className="px-6 py-4">{area.venue_count}</td>
                                    <td className="px-6 py-4">{area.cabin_count}</td>
                                    <td className="px-6 py-4">
                                        <span className="text-green-600 text-xs font-bold bg-green-100 px-2 py-1 rounded-full">High Demand</span>
                                    </td>
                                </tr>
                            ))}
                            {selectedCity.areas.length === 0 && (
                                <tr><td colSpan={4} className="px-6 py-8 text-center text-gray-400">No areas found.</td></tr>
                            )}
                        </tbody>
                    </table>
                </Card>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">City Operations</h2>
                    <p className="text-gray-500">Manage supply and visibility across regions.</p>
                </div>
                <div className="flex gap-2">
                    <Input placeholder="Search cities..." className="min-w-[300px]" />
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {cities.map(city => (
                    <Card
                        key={city.name}
                        className={`p-0 overflow-hidden cursor-pointer transition-all hover:shadow-lg group border-l-4 ${city.is_active ? 'border-l-indigo-500' : 'border-l-gray-300'}`}
                        onClick={() => handleViewCity(city.name)}
                    >
                        <div className="p-6">
                            <div className="flex justify-between items-start mb-4">
                                <div className="flex items-center">
                                    <div className={`p-2 rounded-lg mr-3 ${city.is_active ? 'bg-indigo-50 text-indigo-600' : 'bg-gray-100 text-gray-400'}`}>
                                        <MapPin className="w-6 h-6" />
                                    </div>
                                    <div>
                                        <h3 className={`font-bold text-lg ${city.is_active ? 'text-gray-900' : 'text-gray-500'}`}>{city.name}</h3>
                                        <p className="text-xs text-gray-400">{city.total_venues} Venues</p>
                                    </div>
                                </div>
                                <div onClick={e => e.stopPropagation()}>
                                    <label className="relative inline-flex items-center cursor-pointer">
                                        <input
                                            type="checkbox"
                                            className="sr-only peer"
                                            checked={city.is_active}
                                            onChange={(e) => handleToggleStatus(city.name, city.is_active, e as any)}
                                        />
                                        <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                                    </label>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-gray-100">
                                <div>
                                    <p className="text-xs text-gray-400 uppercase font-bold">Capacity</p>
                                    <p className="font-semibold text-gray-700">{city.total_cabins} <span className="text-xs font-normal">Desks</span></p>
                                </div>
                                <div>
                                    <p className="text-xs text-gray-400 uppercase font-bold">Occupancy</p>
                                    <p className="font-semibold text-gray-700">{city.occupancy_rate}%</p>
                                </div>
                            </div>
                        </div>
                        <div className="bg-gray-50 px-6 py-2 text-xs text-gray-500 flex justify-between group-hover:bg-indigo-50 group-hover:text-indigo-700 transition-colors">
                            <span>View Operational Details</span>
                            <ExternalLink className="w-3 h-3" />
                        </div>
                    </Card>
                ))}
                {cities.length === 0 && !loading && (
                    <div className="col-span-full py-12 text-center text-gray-400">
                        No cities found. Add venues to see them appear here.
                    </div>
                )}
            </div>
        </div>
    );
};
