import React, { useState, useEffect } from 'react';
import { AppState, ReadingRoom } from '../types';
import { WaitlistManager } from '../components/WaitlistManager';
import { venueService } from '../services/venueService';
import { Card, Button } from '../components/UI';
import { Clock, MapPin, ChevronDown } from 'lucide-react';

interface AdminWaitlistsProps {
    state: AppState;
}

export const AdminWaitlists: React.FC<AdminWaitlistsProps> = ({ state }) => {
    const [myVenues, setMyVenues] = useState<ReadingRoom[]>([]);
    const [selectedVenueId, setSelectedVenueId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchVenues = async () => {
            setLoading(true);
            try {
                // Determine source of truth: State or API
                // ideally we use the state if it's populated with *my* venues, but state.readingRooms usually has ALL (or potentially filtered).
                // Let's filter from state first if available and owned by current user.

                const currentUserId = state.currentUser?.id;
                if (!currentUserId) return;

                const owned = state.readingRooms.filter(r => r.ownerId === currentUserId);
                if (owned.length > 0) {
                    setMyVenues(owned);
                    if (!selectedVenueId) setSelectedVenueId(owned[0].id);
                } else {
                    // Fallback to fetching if state is empty (e.g. page refresh)
                    const fetched = await venueService.getMyReadingRooms();
                    setMyVenues(fetched);
                    if (fetched.length > 0 && !selectedVenueId) setSelectedVenueId(fetched[0].id);
                }
            } catch (error) {
                console.error("Failed to load venues for waitlist", error);
            } finally {
                setLoading(false);
            }
        };

        fetchVenues();
    }, [state.currentUser, state.readingRooms]);

    const selectedVenue = myVenues.find(v => v.id === selectedVenueId);

    if (loading) {
        return <div className="p-8 text-center text-gray-500">Loading your venues...</div>;
    }

    if (myVenues.length === 0) {
        return (
            <div className="max-w-4xl mx-auto p-6">
                <Card className="p-8 text-center">
                    <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <h2 className="text-xl font-bold text-gray-900 mb-2">No Reading Rooms Found</h2>
                    <p className="text-gray-500 mb-4">You need to have a listed Reading Room to manage waitlists.</p>
                </Card>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto p-6 space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <Clock className="w-8 h-8 text-indigo-600" />
                        Waitlist Management
                    </h1>
                    <p className="text-gray-500">Manage student waitlists for your reading rooms.</p>
                </div>

                {/* Venue Selector if multiple */}
                {myVenues.length > 1 && (
                    <div className="relative min-w-[250px]">
                        <label className="block text-xs font-semibold text-gray-500 mb-1 uppercase tracking-wide">Select Venue</label>
                        <select
                            className="w-full bg-white border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 block p-2.5"
                            value={selectedVenueId || ''}
                            onChange={(e) => setSelectedVenueId(e.target.value)}
                        >
                            {myVenues.map(venue => (
                                <option key={venue.id} value={venue.id}>
                                    {venue.name}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
            </div>

            {selectedVenue ? (
                <div className="space-y-4">
                    {/* Venue Context Header */}
                    <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-4 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="bg-white p-2 rounded-md shadow-sm">
                                <BuildingIcon className="w-5 h-5 text-indigo-600" />
                            </div>
                            <div>
                                <h3 className="font-bold text-gray-900">{selectedVenue.name}</h3>
                                <p className="text-xs text-indigo-700 flex items-center mt-0.5">
                                    <MapPin className="w-3 h-3 mr-1" /> {selectedVenue.address || selectedVenue.city}
                                </p>
                            </div>
                        </div>
                        <div className="text-right hidden sm:block">
                            <span className="text-xs text-gray-400 font-mono">ID: {selectedVenue.id.slice(0, 8)}...</span>
                        </div>
                    </div>

                    <WaitlistManager readingRoomId={selectedVenue.id} state={state} />
                </div>
            ) : (
                <div className="text-center py-12 text-gray-500 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200">
                    Select a venue to view its waitlist.
                </div>
            )}
        </div>
    );
};

// Start icon helper
const BuildingIcon = ({ className }: { className?: string }) => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
        <rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect>
        <line x1="9" y1="22" x2="9" y2="22.01"></line>
        <line x1="15" y1="22" x2="15" y2="22.01"></line>
        <line x1="12" y1="22" x2="12" y2="22.01"></line>
        <line x1="12" y1="2" x2="12" y2="22"></line>
        <line x1="4" y1="10" x2="20" y2="10"></line>
        <line x1="4" y1="18" x2="20" y2="18"></line>
    </svg>
);
