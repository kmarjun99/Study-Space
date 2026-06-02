import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppState, WaitlistEntry, WaitlistStatus, CabinStatus } from '../types';
import { waitlistService } from '../services/waitlistService';
import { Button, Card, Badge, LiveIndicator } from '../components/UI';
import { toast } from 'react-hot-toast';
import { Clock, MapPin, AlertCircle, CheckCircle, XCircle, ArrowRight } from 'lucide-react';

interface MyWaitlistsProps {
    state: AppState;
    user: any;
    onUpdateWaitlistStatus?: (hasActive: boolean) => void;
}

export const MyWaitlists: React.FC<MyWaitlistsProps> = ({ state, user, onUpdateWaitlistStatus }) => {
    const navigate = useNavigate();
    const [waitlists, setWaitlists] = useState<WaitlistEntry[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchWaitlists = async () => {
        try {
            const data = await waitlistService.getMyWaitlists();
            setWaitlists(data);
            if (data.length === 0 && onUpdateWaitlistStatus) {
                onUpdateWaitlistStatus(false);
            }
        } catch (error) {
            console.error("Failed to fetch waitlists", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchWaitlists();
    }, []);

    const handleCancel = async (id: string) => {
        if (!confirm("Are you sure you want to leave this waitlist?")) return;
        try {
            await waitlistService.cancelWaitlist(id);
            toast.success("Left waitlist.");
            await fetchWaitlists(); // Refresh and check count
        } catch (error) {
            toast.error("Failed to cancel.");
        }
    };

    const handleBook = (entry: WaitlistEntry) => {
        // Navigate to Reading Room Detail Page
        // We could pass a state to open booking modal immediately
        navigate(`/reading-room/${entry.readingRoomId}`, {
            state: {
                autoSelectCabinId: entry.cabinId,
                autoOpenBooking: true
            }
        });
    };

    // Calculate time remaining for NOTIFIED entries
    const getTimeRemaining = (expiresAt?: string) => {
        if (!expiresAt) return null;
        const expiry = new Date(expiresAt).getTime();
        const now = new Date().getTime();
        const diff = expiry - now;
        if (diff <= 0) return "Expired";
        const minutes = Math.floor(diff / 60000);
        return `${minutes} mins left`;
    };

    if (loading) return <div className="p-8 text-center">Loading waitlists...</div>;

    if (waitlists.length === 0) {
        return (
            <div className="max-w-4xl mx-auto px-4 py-12 text-center">
                <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100">
                    <Clock className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                    <h3 className="text-lg font-bold text-gray-900">No Active Waitlists</h3>
                    <p className="text-gray-500 mb-6">You are not waiting for any seats locally.</p>
                    <Button onClick={() => navigate('/student/book')}>Find a Seat</Button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 pb-20">
            <div className="max-w-4xl mx-auto px-4 py-8">
                <h1 className="text-2xl font-bold text-gray-900 mb-6">My Waitlists</h1>

                <div className="space-y-4">
                    {waitlists.map(entry => {
                        // Enrich data
                        const room = state.readingRooms.find(r => r.id === entry.readingRoomId);
                        const cabin = state.cabins.find(c => c.id === entry.cabinId);
                        const expiryText = getTimeRemaining(entry.expiresAt);
                        const isNotified = entry.status === 'NOTIFIED';

                        return (
                            <Card key={entry.id} className={`p-5 transition-shadow hover:shadow-md ${isNotified ? 'border-l-4 border-l-green-500' : ''}`}>
                                <div className="flex flex-col md:flex-row justify-between gap-4">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className="font-bold text-lg text-gray-900">{entry.venueName || room?.name || 'Unknown Venue'}</h3>
                                            <Badge variant={isNotified ? 'success' : 'warning'}>
                                                {entry.status}
                                            </Badge>
                                        </div>
                                        <div className="text-sm text-gray-600 mb-2 flex items-center gap-1">
                                            <MapPin className="w-4 h-4" />
                                            {entry.venueAddress || room?.address || 'Address not available'}
                                        </div>
                                        <div className="flex items-center gap-3 text-sm">
                                            <span className="font-medium bg-gray-100 px-2 py-1 rounded">
                                                Cabin {entry.cabinNumber || cabin?.number || 'N/A'}
                                            </span>
                                            <span className="text-gray-500">
                                                Joined: {new Date(entry.date).toLocaleDateString()}
                                            </span>
                                        </div>

                                        {isNotified && (
                                            <div className="mt-3 bg-green-50 text-green-800 px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
                                                <AlertCircle className="w-4 h-4" />
                                                Seat is reserved for you! {expiryText}
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex flex-col gap-2 justify-center min-w-[140px]">
                                        {isNotified ? (
                                            <Button onClick={() => handleBook(entry)} className="w-full bg-green-600 hover:bg-green-700">
                                                Book Now
                                            </Button>
                                        ) : (
                                            <div className="text-center text-xs text-gray-500 italic py-2">
                                                Position: {entry.priorityPosition || '-'}
                                            </div>
                                        )}

                                        <Button
                                            variant="outline"
                                            className="w-full text-red-600 border-red-200 hover:bg-red-50"
                                            onClick={() => handleCancel(entry.id)}
                                        >
                                            Leave Waitlist
                                        </Button>
                                    </div>
                                </div>
                            </Card>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};
