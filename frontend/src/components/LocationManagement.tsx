/**
 * LocationManagement - Super Admin component for managing locations (cities/localities)
 */
import React, { useState, useEffect } from 'react';
import { Card, Button, Input, Modal, Badge } from './UI';
import { locationService, LocationDetails } from '../services/locationService';
import { MapPin, Plus, Edit2, Trash2, Search, CheckCircle, XCircle, Loader2, RefreshCw } from 'lucide-react';

// Indian states for dropdown
const INDIAN_STATES = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
    'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
    'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
    'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
    'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
    'Delhi', 'Chandigarh', 'Puducherry'
];

interface LocationFormData {
    state: string;
    city: string;
    locality: string;
    latitude: string;
    longitude: string;
}

const emptyForm: LocationFormData = {
    state: '',
    city: '',
    locality: '',
    latitude: '',
    longitude: ''
};

export const LocationManagement: React.FC = () => {
    const [locations, setLocations] = useState<LocationDetails[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [stateFilter, setStateFilter] = useState('');

    // Modal state
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [formData, setFormData] = useState<LocationFormData>(emptyForm);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Fetch locations
    const fetchLocations = async () => {
        setIsLoading(true);
        try {
            const data = await locationService.getAllAdmin();
            setLocations(data);
        } catch (err) {
            console.error('Failed to fetch locations:', err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchLocations();
    }, []);

    // Filter locations
    const filteredLocations = locations.filter(loc => {
        const matchesSearch = searchQuery === '' ||
            loc.city.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (loc.locality || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
            loc.state.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesState = stateFilter === '' || loc.state === stateFilter;

        return matchesSearch && matchesState;
    });

    // Get unique states from locations
    const usedStates = [...new Set(locations.map(l => l.state))].sort();

    // Open modal for create/edit
    const openCreateModal = () => {
        setEditingId(null);
        setFormData(emptyForm);
        setError(null);
        setIsModalOpen(true);
    };

    const openEditModal = (location: LocationDetails) => {
        setEditingId(location.id);
        setFormData({
            state: location.state,
            city: location.city,
            locality: location.locality || '',
            latitude: location.latitude?.toString() || '',
            longitude: location.longitude?.toString() || ''
        });
        setError(null);
        setIsModalOpen(true);
    };

    // Save location
    const handleSave = async () => {
        if (!formData.state || !formData.city) {
            setError('State and City are required');
            return;
        }

        setIsSaving(true);
        setError(null);

        try {
            const payload = {
                state: formData.state,
                city: formData.city,
                locality: formData.locality || undefined,
                latitude: formData.latitude ? parseFloat(formData.latitude) : undefined,
                longitude: formData.longitude ? parseFloat(formData.longitude) : undefined
            };

            if (editingId) {
                await locationService.update(editingId, payload);
            } else {
                await locationService.create(payload);
            }

            setIsModalOpen(false);
            fetchLocations();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to save location');
        } finally {
            setIsSaving(false);
        }
    };

    // Delete location
    const handleDelete = async (id: string, displayName: string) => {
        if (!confirm(`Deactivate location "${displayName}"? It will no longer appear in search.`)) {
            return;
        }

        try {
            await locationService.delete(id);
            fetchLocations();
        } catch (err) {
            alert('Failed to delete location');
        }
    };

    // Toggle active status
    const toggleActive = async (location: LocationDetails) => {
        try {
            await locationService.update(location.id, { is_active: !location.is_active });
            fetchLocations();
        } catch (err) {
            alert('Failed to update location status');
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                        <MapPin className="w-5 h-5 text-indigo-600" />
                        Location Management
                    </h2>
                    <p className="text-gray-500 text-sm">Manage cities and localities for location search</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={fetchLocations}>
                        <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                    </Button>
                    <Button onClick={openCreateModal}>
                        <Plus className="w-4 h-4 mr-1" /> Add Location
                    </Button>
                </div>
            </div>

            {/* Filters */}
            <Card className="p-4">
                <div className="flex flex-col md:flex-row gap-4">
                    <div className="flex-1 relative">
                        <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
                        <input
                            type="text"
                            placeholder="Search city, locality, or state..."
                            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                    <select
                        className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
                        value={stateFilter}
                        onChange={(e) => setStateFilter(e.target.value)}
                    >
                        <option value="">All States</option>
                        {usedStates.map(state => (
                            <option key={state} value={state}>{state}</option>
                        ))}
                    </select>
                </div>
            </Card>

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="p-4 text-center">
                    <div className="text-2xl font-bold text-indigo-600">{locations.length}</div>
                    <div className="text-xs text-gray-500">Total Locations</div>
                </Card>
                <Card className="p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">{locations.filter(l => l.is_active).length}</div>
                    <div className="text-xs text-gray-500">Active</div>
                </Card>
                <Card className="p-4 text-center">
                    <div className="text-2xl font-bold text-gray-600">{usedStates.length}</div>
                    <div className="text-xs text-gray-500">States</div>
                </Card>
                <Card className="p-4 text-center">
                    <div className="text-2xl font-bold text-amber-600">{[...new Set(locations.map(l => l.city))].length}</div>
                    <div className="text-xs text-gray-500">Cities</div>
                </Card>
            </div>

            {/* Locations Table */}
            <Card className="overflow-hidden">
                {isLoading ? (
                    <div className="p-12 text-center">
                        <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-2" />
                        <p className="text-gray-500">Loading locations...</p>
                    </div>
                ) : filteredLocations.length === 0 ? (
                    <div className="p-12 text-center text-gray-500">
                        <MapPin className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                        <p className="font-medium">No locations found</p>
                        <p className="text-sm">Try changing your search or add a new location.</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">State</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">City</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Locality</th>
                                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Usage</th>
                                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">Status</th>
                                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {filteredLocations.map(loc => (
                                    <tr key={loc.id} className={!loc.is_active ? 'bg-gray-50 opacity-60' : ''}>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{loc.state}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{loc.city}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{loc.locality || '-'}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                                            <span className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded-full text-xs font-medium">
                                                {loc.usage_count}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-center">
                                            <button onClick={() => toggleActive(loc)} title={loc.is_active ? 'Click to deactivate' : 'Click to activate'}>
                                                {loc.is_active ? (
                                                    <span className="px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium flex items-center gap-1 justify-center">
                                                        <CheckCircle className="w-3 h-3" /> Active
                                                    </span>
                                                ) : (
                                                    <span className="px-2 py-1 bg-gray-100 text-gray-500 rounded-full text-xs font-medium flex items-center gap-1 justify-center">
                                                        <XCircle className="w-3 h-3" /> Inactive
                                                    </span>
                                                )}
                                            </button>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                            <button onClick={() => openEditModal(loc)} className="text-indigo-600 hover:text-indigo-900 mr-3">
                                                <Edit2 className="w-4 h-4" />
                                            </button>
                                            <button onClick={() => handleDelete(loc.id, loc.displayName)} className="text-red-600 hover:text-red-900">
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </Card>

            {/* Add/Edit Modal */}
            <Modal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                title={editingId ? 'Edit Location' : 'Add New Location'}
            >
                <div className="space-y-4">
                    {error && (
                        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                            {error}
                        </div>
                    )}

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">State *</label>
                        <select
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white"
                            value={formData.state}
                            onChange={(e) => setFormData({ ...formData, state: e.target.value })}
                        >
                            <option value="">Select State</option>
                            {INDIAN_STATES.map(state => (
                                <option key={state} value={state}>{state}</option>
                            ))}
                        </select>
                    </div>

                    <Input
                        label="City *"
                        value={formData.city}
                        onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                        placeholder="e.g., Mumbai, Bangalore"
                    />

                    <Input
                        label="Locality (Optional)"
                        value={formData.locality}
                        onChange={(e) => setFormData({ ...formData, locality: e.target.value })}
                        placeholder="e.g., Koramangala, Indiranagar"
                    />

                    <div className="grid grid-cols-2 gap-4">
                        <Input
                            label="Latitude"
                            type="number"
                            step="any"
                            value={formData.latitude}
                            onChange={(e) => setFormData({ ...formData, latitude: e.target.value })}
                            placeholder="e.g., 12.9716"
                        />
                        <Input
                            label="Longitude"
                            type="number"
                            step="any"
                            value={formData.longitude}
                            onChange={(e) => setFormData({ ...formData, longitude: e.target.value })}
                            placeholder="e.g., 77.5946"
                        />
                    </div>

                    <p className="text-xs text-gray-500">
                        💡 Tip: You can get coordinates from Google Maps by right-clicking on a location.
                    </p>

                    <div className="flex gap-3 pt-4">
                        <Button variant="outline" className="flex-1" onClick={() => setIsModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button className="flex-1" onClick={handleSave} disabled={isSaving}>
                            {isSaving ? 'Saving...' : editingId ? 'Update Location' : 'Add Location'}
                        </Button>
                    </div>
                </div>
            </Modal>
        </div>
    );
};

export default LocationManagement;
