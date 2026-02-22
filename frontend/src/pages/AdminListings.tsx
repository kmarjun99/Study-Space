/**
 * AdminListings - Unified listings dashboard for owners
 * Shows all Reading Rooms and PG/Hostels owned by the current user
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ReadingRoom, Accommodation, ListingStatus } from '../types';
import { Card, Button, Badge } from '../components/UI';
import { venueService } from '../services/venueService';
import { supplyService } from '../services/supplyService';
import { trustService, TrustFlag } from '../services/trustService';
import {
    Building2, Home, Plus, MapPin, CheckCircle, Clock, AlertTriangle,
    XCircle, Loader2, Eye, Edit2, Zap, ArrowRight, Trash2, ShieldAlert
} from 'lucide-react';

export const AdminListings: React.FC = () => {
    const navigate = useNavigate();
    const [readingRooms, setReadingRooms] = useState<ReadingRoom[]>([]);
    const [accommodations, setAccommodations] = useState<Accommodation[]>([]);
    const [activeFlags, setActiveFlags] = useState<TrustFlag[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        fetchListings();
    }, []);

    const fetchListings = async () => {
        setIsLoading(true);
        try {
            const [venues, accs] = await Promise.all([
                venueService.getMyReadingRooms(),
                supplyService.getMyAccommodations()
            ]);
            setReadingRooms(venues);
            setAccommodations(accs);

            // Fetch owner's flags to show correct status
            try {
                // We need to get current user ID - get it from localStorage or context
                const userStr = localStorage.getItem('studySpace_user');
                if (userStr) {
                    const user = JSON.parse(userStr);
                    if (user?.id) {
                        const flags = await trustService.getOwnerFlags(user.id);
                        // Filter for active (unresolved) flags
                        const active = flags.filter(f => f.status !== 'resolved');
                        setActiveFlags(active);
                    }
                }
            } catch (flagErr) {
                console.warn('Could not fetch flags:', flagErr);
            }
        } catch (error) {
            console.error('Failed to fetch listings:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleDelete = async (id: string, type: 'reading-room' | 'accommodation', name: string) => {
        if (!window.confirm(`Are you sure you want to delete "${name}"? This action cannot be undone.`)) {
            return;
        }

        try {
            if (type === 'reading-room') {
                await venueService.deleteReadingRoom(id);
                setReadingRooms(prev => prev.filter(r => r.id !== id));
            } else {
                await supplyService.deleteAccommodation(id);
                setAccommodations(prev => prev.filter(a => a.id !== id));
            }
        } catch (error: any) {
            console.error('Failed to delete:', error);
            const errorMessage = error.response?.data?.detail || 'Failed to delete. Please try again.';
            alert(errorMessage);
        }
    };

    const getStatusBadge = (status: ListingStatus, entityId?: string) => {
        // Check if this entity has an active flag - if so, override the status
        if (entityId) {
            const entityFlag = activeFlags.find(f => f.entity_id === entityId);
            if (entityFlag) {
                // Show flag status instead of listing status
                const isSevere = entityFlag.status === 'escalated' || entityFlag.status === 'rejected';
                return (
                    <Badge variant={isSevere ? 'error' : 'warning'} className="flex items-center gap-1">
                        {isSevere ? <XCircle className="w-3 h-3" /> : <ShieldAlert className="w-3 h-3" />}
                        {isSevere ? 'Suspended' : 'Flagged'}
                    </Badge>
                );
            }
        }

        const config: Record<ListingStatus, { variant: 'success' | 'warning' | 'error' | 'info'; icon: React.ReactNode; label: string }> = {
            LIVE: { variant: 'success', icon: <CheckCircle className="w-3 h-3" />, label: 'Live' },
            VERIFICATION_PENDING: { variant: 'warning', icon: <Clock className="w-3 h-3" />, label: 'Pending' },
            PAYMENT_PENDING: { variant: 'warning', icon: <AlertTriangle className="w-3 h-3" />, label: 'Payment Pending' },
            DRAFT: { variant: 'info', icon: <Edit2 className="w-3 h-3" />, label: 'Draft' },
            REJECTED: { variant: 'error', icon: <XCircle className="w-3 h-3" />, label: 'Rejected' },
            SUSPENDED: { variant: 'error', icon: <XCircle className="w-3 h-3" />, label: 'Suspended' }
        };
        const { variant, icon, label } = config[status] || config.DRAFT;
        return (
            <Badge variant={variant} className="flex items-center gap-1">
                {icon} {label}
            </Badge>
        );
    };

    const ListingCard = ({
        id,
        name,
        location,
        status,
        type,
        imageUrl,
        onClick,
        onDelete
    }: {
        id: string;
        name: string;
        location: string;
        status: ListingStatus;
        type: 'reading-room' | 'accommodation';
        imageUrl?: string;
        onClick: () => void;
        onDelete: () => void;
    }) => (
        <Card
            className="p-4 hover:shadow-lg transition-all cursor-pointer group"
            onClick={onClick}
        >
            <div className="flex gap-4">
                {/* Image */}
                <div className="w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden bg-gray-100">
                    {imageUrl ? (
                        <img src={imageUrl} alt={name} className="w-full h-full object-cover" />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400">
                            {type === 'reading-room' ? <Building2 className="w-8 h-8" /> : <Home className="w-8 h-8" />}
                        </div>
                    )}
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                        <h3 className="font-semibold text-gray-900 truncate group-hover:text-indigo-600 transition-colors">
                            {name}
                        </h3>
                        {getStatusBadge(status, id)}
                    </div>
                    <p className="text-sm text-gray-500 flex items-center gap-1 mt-1">
                        <MapPin className="w-3 h-3" /> {location || 'No location set'}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                        {type === 'reading-room' ? 'Reading Room / Study Space' : 'PG / Hostel'}
                    </p>
                </div>

                {/* Arrow */}
                <div className="flex flex-col items-center gap-2">
                    <button
                        onClick={(e) => { e.stopPropagation(); onDelete(); }}
                        className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                        title="Delete"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                    <div className="text-gray-300 group-hover:text-indigo-600 transition-colors">
                        <ArrowRight className="w-5 h-5" />
                    </div>
                </div>
            </div>
        </Card>
    );

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center py-20">
                <Loader2 className="w-10 h-10 animate-spin text-indigo-600 mb-4" />
                <p className="text-gray-500">Loading your listings...</p>
            </div>
        );
    }

    const totalListings = readingRooms.length + accommodations.length;

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">My Listings</h1>
                    <p className="text-gray-500">Manage all your Reading Rooms and PG/Hostels</p>
                </div>
                <div className="flex gap-3">
                    <Button
                        variant="outline"
                        onClick={() => navigate('/admin/venue/new')}
                        className="border-purple-300 text-purple-700 hover:bg-purple-50"
                    >
                        <Plus className="w-4 h-4 mr-2" />
                        Add Reading Room
                    </Button>
                    <Button
                        onClick={() => navigate('/admin/accommodation/new')}
                        className="bg-purple-600 hover:bg-purple-700"
                    >
                        <Plus className="w-4 h-4 mr-2" />
                        Add Property
                    </Button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="p-4 text-center">
                    <div className="text-2xl font-bold text-indigo-600">{totalListings}</div>
                    <div className="text-xs text-gray-500">Total Listings</div>
                </Card>
                <Card className="p-4 text-center">
                    <div className="text-2xl font-bold text-blue-600">{readingRooms.length}</div>
                    <div className="text-xs text-gray-500">Reading Rooms</div>
                </Card>
                <Card className="p-4 text-center">
                    <div className="text-2xl font-bold text-purple-600">{accommodations.length}</div>
                    <div className="text-xs text-gray-500">Properties</div>
                </Card>
                <Card className="p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">
                        {readingRooms.filter(r => r.status === 'LIVE').length + accommodations.filter(a => a.status === 'LIVE').length}
                    </div>
                    <div className="text-xs text-gray-500">Live Listings</div>
                </Card>
            </div>

            {/* Empty State */}
            {totalListings === 0 && (
                <Card className="p-12 text-center">
                    <Building2 className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">No Listings Yet</h3>
                    <p className="text-gray-500 mb-6 max-w-md mx-auto">
                        Start by adding your first Reading Room or Property. Each listing can be verified and managed independently.
                    </p>
                    <div className="flex justify-center gap-4">
                        <Button variant="outline" onClick={() => navigate('/admin/venue/new')}>
                            <Building2 className="w-4 h-4 mr-2" /> Add Reading Room
                        </Button>
                        <Button onClick={() => navigate('/admin/accommodation/new')}>
                            <Home className="w-4 h-4 mr-2" /> Add Property
                        </Button>
                    </div>
                </Card>
            )}

            {/* Reading Rooms Section */}
            {readingRooms.length > 0 && (
                <div>
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                            <Building2 className="w-5 h-5 text-indigo-600" />
                            Reading Rooms ({readingRooms.length})
                        </h2>
                        <Button size="sm" className="bg-purple-600 hover:bg-purple-700 text-white" onClick={() => navigate('/admin/venue/new')}>
                            <Plus className="w-4 h-4 mr-1" /> Add New
                        </Button>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        {readingRooms.map(room => (
                            <ListingCard
                                key={room.id}
                                id={room.id}
                                name={room.name}
                                location={room.city ? `${room.locality || room.area || ''}, ${room.city}`.replace(/^, /, '') : room.address}
                                status={room.status as ListingStatus}
                                type="reading-room"
                                imageUrl={room.imageUrl}
                                onClick={() => navigate(`/admin/venue/${room.id}`)}
                                onDelete={() => handleDelete(room.id, 'reading-room', room.name)}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Accommodations Section */}
            {accommodations.length > 0 && (
                <div>
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                            <Home className="w-5 h-5 text-purple-600" />
                            PG / Hostels ({accommodations.length})
                        </h2>
                        <Button size="sm" className="bg-purple-600 hover:bg-purple-700 text-white" onClick={() => navigate('/admin/accommodation/new')}>
                            <Plus className="w-4 h-4 mr-1" /> Add New
                        </Button>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        {accommodations.map(acc => (
                            <ListingCard
                                key={acc.id}
                                id={acc.id}
                                name={acc.name}
                                location={acc.city ? `${acc.locality || acc.area || ''}, ${acc.city}`.replace(/^, /, '') : acc.address}
                                status={acc.status as ListingStatus}
                                type="accommodation"
                                imageUrl={acc.imageUrl}
                                onClick={() => navigate(`/admin/accommodation/${acc.id}`)}
                                onDelete={() => handleDelete(acc.id, 'accommodation', acc.name)}
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default AdminListings;
