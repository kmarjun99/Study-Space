import React, { useEffect, useState } from 'react';
import { WaitlistEntry, AppState } from '../types';
import { waitlistService } from '../services/waitlistService';
import { Card, Badge, Button } from '../components/UI';
import { Clock, User, XCircle, CheckCircle, AlertCircle } from 'lucide-react';
import { toast } from 'react-hot-toast';

interface WaitlistManagerProps {
    readingRoomId: string;
    state: AppState;
}

export const WaitlistManager: React.FC<WaitlistManagerProps> = ({ readingRoomId, state }) => {
    const [entries, setEntries] = useState<WaitlistEntry[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchWaitlist = async () => {
        setLoading(true);
        try {
            // Note: In real app, we need an endpoint to get ALL waitlists for a venue (owner view)
            // For now, filtering from specific service call or using mock if backend not ready for "get venue waitlists"
            // Re-using the getMyWaitlists for student isn't right.
            // Assumption: we need a new service method `getVenueWaitlist`
            // Let's implement a quick fetch for now using the existing list if possible or mocking

            // In a real scenario we'd call: const data = await waitlistService.getVenueWaitlist(readingRoomId);
            // Since we haven't implemented that specific endpoint in frontend service yet, let's assume valid data comes
            // from the backend if we did.
            // For this task, we will simulate or add the missing service method.

            // Let's assume we add `getVenueWaitlist` to waitlistService
            const data = await waitlistService.getVenueWaitlist(readingRoomId);
            setEntries(data);
        } catch (error) {
            console.error("Failed to load waitlist", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchWaitlist();
    }, [readingRoomId]);

    const handleRemove = async (entryId: string) => {
        if (!confirm("Remove this user from the waitlist?")) return;
        try {
            await waitlistService.cancelWaitlist(entryId); // Owners can cancel too
            toast.success("User removed from waitlist");
            fetchWaitlist();
        } catch (e) {
            toast.error("Failed to remove user");
        }
    };

    if (loading) return <div className="p-4 text-center text-gray-500">Loading waitlist...</div>;

    if (entries.length === 0) {
        return (
            <Card className="p-8 text-center text-gray-500">
                <Clock className="w-10 h-10 mx-auto mb-2 text-gray-300" />
                <p>No active waitlist entries for this venue.</p>
            </Card>
        );
    }

    return (
        <Card className="p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                <Clock className="w-5 h-5 mr-2 text-indigo-600" />
                Waitlist Management ({entries.length})
            </h3>

            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">#</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cabin</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Action</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {entries.map((entry, index) => {
                            // Fallback lookup if enriched data invalid (unlikely)
                            const cabin = state.cabins.find(c => c.id === entry.cabinId);
                            const isNotified = entry.status === 'NOTIFIED';

                            return (
                                <tr key={entry.id}>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                        {index + 1}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center">
                                            <div className="h-8 w-8 rounded-full bg-gray-200 flex items-center justify-center text-gray-500 mr-3">
                                                <User className="w-4 h-4" />
                                            </div>
                                            <div>
                                                <div className="text-sm font-medium text-gray-900">{entry.userName || 'Unknown User'}</div>
                                                <div className="text-xs text-gray-500">{entry.userEmail}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {entry.cabinNumber ? `Cabin ${entry.cabinNumber}` : (cabin ? `Cabin ${cabin.number}` : 'Any')}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <Badge variant={isNotified ? 'success' : 'warning'}>
                                            {entry.status}
                                        </Badge>
                                        {isNotified && entry.expiresAt && (
                                            <div className="text-xs text-red-500 mt-1 flex items-center">
                                                <AlertCircle className="w-3 h-3 mr-1" />
                                                Expires: {new Date(entry.expiresAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </div>
                                        )}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {new Date(entry.date).toLocaleDateString()}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                        <button
                                            onClick={() => handleRemove(entry.id)}
                                            className="text-red-600 hover:text-red-900"
                                        >
                                            Remove
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </Card>
    );
};
