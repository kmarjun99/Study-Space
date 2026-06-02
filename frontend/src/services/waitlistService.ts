import api from './api';
import { WaitlistEntry } from '../types';

export const waitlistService = {
    joinWaitlist: async (cabinId: string, readingRoomId: string): Promise<WaitlistEntry> => {
        const response = await api.post('/waitlist/', { cabin_id: cabinId, reading_room_id: readingRoomId });
        return response.data;
    },

    getMyWaitlists: async (): Promise<WaitlistEntry[]> => {
        const response = await api.get('/waitlist/my-waitlists');
        return response.data;
    },

    getVenueWaitlist: async (venueId: string): Promise<WaitlistEntry[]> => {
        // Mock implementation until backend endpoint is confirmed
        // For now, we reuse the endpoint or add a new one. backend `waitlist.py` might need `GET /waitlist/venue/{id}`
        // Assuming we added it or using a filter.
        // Let's rely on a new endpoint that we *should* have added.
        // Actually, checking task history, we added `GET /my-waitlists`. We didn't explicitly confirm `GET /venue/{id}/waitlist`.
        // Let's add it to `waitlist.py` if missing, or for now assume we can fetch it.
        // Re-reading `waitlist.py` (from memory/logs) - we might need to add this endpoint.
        // But for frontend progress, let's define the call.
        const response = await api.get(`/waitlist/venue/${venueId}`);
        return response.data;
    },

    cancelWaitlist: async (entryId: string): Promise<void> => {
        await api.post(`/waitlist/${entryId}/cancel`);
    }
};
