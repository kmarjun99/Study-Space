
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { Building2, ExternalLink } from 'lucide-react';
import { supplyService } from '../services/supplyService';

export const SuperAdminSupplyView = () => {
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<'VENUES' | 'ACCOMMODATIONS'>('VENUES');
    const [venues, setVenues] = useState<any[]>([]); // Using any for rapid proto, ideally typed
    const [accommodations, setAccommodations] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadSupply();
    }, []);

    const loadSupply = async () => {
        setLoading(true);
        try {
            const [vData, aData] = await Promise.all([
                supplyService.getAllReadingRooms(true),
                supplyService.getAllAccommodations(true)
            ]);
            setVenues(vData);
            setAccommodations(aData);
        } catch (err) {
            console.error("Failed to load supply", err);
        } finally {
            setLoading(false);
        }
    };

    const handleVerify = async (id: string, type: 'room' | 'accommodation') => {
        try {
            await supplyService.verifyEntity(id, type);
            // Optimistic update
            if (type === 'room') {
                setVenues(prev => prev.map(v => v.id === id ? { ...v, is_verified: true } : v));
            } else {
                setAccommodations(prev => prev.map(a => a.id === id ? { ...a, is_verified: true } : a));
            }
        } catch (err) {
            console.error("Failed to verify", err);
            alert("Failed to verify. Ensure you have permission.");
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Supply Management</h2>
                    <p className="text-gray-500">Overview of all active venues and housing units.</p>
                </div>
            </div>

            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="p-6 border-l-4 border-l-indigo-500">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Total Venues</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{venues.length}</p>
                    <p className="text-xs text-indigo-600 mt-1">Study Spaces</p>
                </Card>
                <Card className="p-6 border-l-4 border-l-blue-500">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Total Housing</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{accommodations.length}</p>
                    <p className="text-xs text-blue-600 mt-1">Hostels & PGs</p>
                </Card>
                <Card className="p-6 border-l-4 border-l-green-500">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Total Capacity</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">
                        {/* Rough estimate or robust calc */}
                        {venues.length * 50 + accommodations.length * 20}
                    </p>
                    <p className="text-xs text-green-600 mt-1">Approx. Inventory</p>
                </Card>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-200">
                <nav className="-mb-px flex space-x-8">
                    <button
                        onClick={() => setActiveTab('VENUES')}
                        className={`${activeTab === 'VENUES'
                            ? 'border-indigo-500 text-indigo-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
                    >
                        Reading Rooms
                    </button>
                    <button
                        onClick={() => setActiveTab('ACCOMMODATIONS')}
                        className={`${activeTab === 'ACCOMMODATIONS'
                            ? 'border-indigo-500 text-indigo-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
                    >
                        Accommodations (Housing)
                    </button>
                </nav>
            </div>

            {/* Content Table */}
            <Card className="p-0 overflow-hidden border border-gray-200 shadow-sm min-h-[400px]">
                {loading ? (
                    <div className="flex justify-center items-center h-40 text-gray-400">Loading supply data...</div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm text-gray-500">
                            <thead className="bg-gray-50 text-xs uppercase text-gray-700 font-semibold">
                                <tr>
                                    <th className="px-6 py-4">Name</th>
                                    <th className="px-6 py-4">Location</th>
                                    <th className="px-6 py-4">Price</th>
                                    <th className="px-6 py-4">Contact</th>
                                    <th className="px-6 py-4">Status</th>
                                    <th className="px-6 py-4">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {activeTab === 'VENUES' ? (
                                    venues.length > 0 ? venues.map(v => (
                                        <tr key={v.id} className="bg-white hover:bg-gray-50 transition-colors">
                                            <td className="px-6 py-4">
                                                <div className="flex items-center">
                                                    <div className="h-10 w-10 flex-shrink-0 mr-4 bg-gray-100 rounded-lg overflow-hidden">
                                                        {v.imageUrl ? <img src={v.imageUrl} alt="" className="h-full w-full object-cover" /> : <Building2 className="p-2 h-full w-full text-gray-400" />}
                                                    </div>
                                                    <div>
                                                        <div className="font-medium text-gray-900">{v.name}</div>
                                                        <div className="text-gray-500 text-xs">Prop ID: {v.id.slice(0, 8)}</div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="text-gray-900">{v.city || 'N/A'}</div>
                                                <div className="text-xs">{v.area || v.address}</div>
                                            </td>
                                            <td className="px-6 py-4 text-gray-900">₹{v.priceStart}/mo</td>
                                            <td className="px-6 py-4 text-gray-500">{v.contactPhone}</td>
                                            <td className="px-6 py-4">
                                                {v.is_verified ? (
                                                    <Badge variant="success">Verified</Badge>
                                                ) : v.status === 'REJECTED' ? (
                                                    <Badge variant="error">Rejected</Badge>
                                                ) : (
                                                    <Badge variant="warning">Pending</Badge>
                                                )}
                                            </td>
                                            <td className="px-6 py-4 flex gap-2">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                                                    onClick={() => navigate(`/super-admin/reading-rooms/${v.id}/review`)}
                                                >
                                                    Review
                                                </Button>
                                            </td>
                                        </tr>
                                    )) : <tr><td colSpan={6} className="px-6 py-8 text-center bg-gray-50/50">No reading rooms found.</td></tr>
                                ) : (
                                    accommodations.length > 0 ? accommodations.map(a => (
                                        <tr key={a.id} className="bg-white hover:bg-gray-50 transition-colors">
                                            <td className="px-6 py-4">
                                                <div className="flex items-center">
                                                    <div className="h-10 w-10 flex-shrink-0 mr-4 bg-gray-100 rounded-lg overflow-hidden">
                                                        {a.imageUrl ? <img src={a.imageUrl} alt="" className="h-full w-full object-cover" /> : <Building2 className="p-2 h-full w-full text-gray-400" />}
                                                    </div>
                                                    <div>
                                                        <div className="font-medium text-gray-900">{a.name}</div>
                                                        <div className="text-gray-500 text-xs">{a.type} • {a.gender}</div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="text-gray-900">{a.city || 'N/A'}</div>
                                                <div className="text-xs">{a.address}</div>
                                            </td>
                                            <td className="px-6 py-4 text-gray-900">₹{a.price}/mo</td>
                                            <td className="px-6 py-4 text-gray-500">{a.contactPhone}</td>
                                            <td className="px-6 py-4">
                                                {a.is_verified ? (
                                                    <Badge variant="success">Verified</Badge>
                                                ) : (
                                                    <Badge variant="warning">Pending</Badge>
                                                )}
                                            </td>
                                            <td className="px-6 py-4 flex gap-2">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="text-indigo-600 border-indigo-200 hover:bg-indigo-50"
                                                    onClick={() => navigate(`/super-admin/accommodations/${a.id}/review`)}
                                                >
                                                    Review
                                                </Button>
                                            </td>
                                        </tr>
                                    )) : <tr><td colSpan={6} className="px-6 py-8 text-center bg-gray-50/50">No accommodations found.</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </Card>
        </div>
    );
};
