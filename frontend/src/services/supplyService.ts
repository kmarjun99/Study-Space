
import api from './api';
import { ReadingRoom, Accommodation } from '../types';

export const supplyService = {
    getAllReadingRooms: async (includeUnverified = false): Promise<ReadingRoom[]> => {
        // Re-use current backend endpoint, but explicitly for admin usage if needed later.
        const response = await api.get('/reading-rooms/', {
            params: { include_unverified: includeUnverified }
        });
        return response.data.map((room: any) => ({
            ...room,
            imageUrl: room.image_url,
            ownerId: room.owner_id,
            priceStart: room.price_start,
            contactPhone: room.contact_phone,
            amenities: Array.isArray(room.amenities)
                ? room.amenities
                : (typeof room.amenities === 'string' ? room.amenities.split(',') : []),
        }));
    },

    getAllAccommodations: async (includeUnverified = false, limit = 100): Promise<Accommodation[]> => {
        try {
            const response = await api.get('/accommodations/', {
                params: { include_unverified: includeUnverified, limit: limit }
            });
            // Defensive checks: ensure response.data is an array
            if (!response.data || !Array.isArray(response.data)) {
                console.warn('Accommodations API returned invalid data, using empty array');
                return [];
            }
            return response.data.map((acc: any) => ({
                ...acc,
                ownerId: acc.owner_id || '',
                imageUrl: acc.image_url || '',
                contactPhone: acc.contact_phone || '',
                amenities: Array.isArray(acc.amenities)
                    ? acc.amenities
                    : (typeof acc.amenities === 'string' && acc.amenities ? acc.amenities.split(',') : []),
            }));
        } catch (error) {
            console.error('Failed to fetch accommodations:', error);
            return []; // Return empty array on error to prevent crash
        }
    },

    getMyAccommodations: async (): Promise<Accommodation[]> => {
        try {
            const response = await api.get('/accommodations/my');
            if (!response.data || !Array.isArray(response.data)) {
                return [];
            }
            return response.data.map((acc: any) => ({
                ...acc,
                ownerId: acc.owner_id || '',
                imageUrl: acc.image_url || '',
                contactPhone: acc.contact_phone || '',
                amenities: Array.isArray(acc.amenities)
                    ? acc.amenities
                    : (typeof acc.amenities === 'string' && acc.amenities ? acc.amenities.split(',') : []),
            }));
        } catch (error) {
            console.error('Failed to fetch my accommodations:', error);
            return [];
        }
    },

    deleteAccommodation: async (accId: string): Promise<void> => {
        await api.delete(`/accommodations/${accId}`);
    },

    createReadingRoom: async (data: Partial<ReadingRoom>): Promise<ReadingRoom> => {
        const payload: any = {
            name: data.name,
            description: data.description || '',
            address: data.address,
            price_start: data.priceStart,
            amenities: data.amenities?.join(','),
            images: data.images, // JSON string
            image_url: data.imageUrl,
            contact_phone: data.contactPhone,
            city: data.city,
            area: data.area,
            locality: data.locality,
            state: data.state,
            pincode: data.pincode,
            location_id: data.locationId,
        };
        const response = await api.post('/reading-rooms/', payload);
        return response.data;
    },

    getReadingRoomById: async (id: string): Promise<ReadingRoom> => {
        const response = await api.get(`/reading-rooms/${id}`);
        const room = response.data;
        return {
            ...room,
            imageUrl: room.image_url,
            ownerId: room.owner_id,
            priceStart: room.price_start,
            contactPhone: room.contact_phone,
            amenities: Array.isArray(room.amenities)
                ? room.amenities
                : (typeof room.amenities === 'string' ? room.amenities.split(',') : []),
        };
    },

    createAccommodation: async (data: Partial<Accommodation>): Promise<Accommodation> => {
        const payload: any = {
            name: data.name,
            type: data.type,
            gender: data.gender,
            address: data.address,
            price: data.price,
            sharing: data.sharing,
            amenities: data.amenities?.join(','),
            images: data.images, // JSON string
            image_url: data.imageUrl,
            contact_phone: data.contactPhone,
            rating: data.rating,
            city: data.city,
            area: data.area,
            locality: data.locality,
            state: data.state,
            pincode: data.pincode,
        };
        const response = await api.post('/accommodations/', payload);
        const acc = response.data;
        return {
            ...acc,
            ownerId: acc.owner_id,
            imageUrl: acc.image_url,
            images: acc.images,
            contactPhone: acc.contact_phone,
            amenities: Array.isArray(acc.amenities)
                ? acc.amenities
                : (typeof acc.amenities === 'string' ? acc.amenities.split(',') : []),
            status: acc.status,
            isVerified: acc.is_verified
        };
    },

    updateAccommodation: async (id: string, updates: Partial<Accommodation>): Promise<Accommodation> => {
        const payload: any = {};
        if (updates.name !== undefined) payload.name = updates.name;
        if (updates.type !== undefined) payload.type = updates.type;
        if (updates.gender !== undefined) payload.gender = updates.gender;
        if (updates.address !== undefined) payload.address = updates.address;
        if (updates.price !== undefined) payload.price = updates.price;
        if (updates.sharing !== undefined) payload.sharing = updates.sharing;
        if (updates.imageUrl !== undefined) payload.image_url = updates.imageUrl;
        if (updates.images !== undefined) payload.images = updates.images;
        if (updates.contactPhone !== undefined) payload.contact_phone = updates.contactPhone;
        if (updates.city !== undefined) payload.city = updates.city;
        if (updates.area !== undefined) payload.area = updates.area;
        if (updates.locality !== undefined) payload.locality = updates.locality;
        if (updates.state !== undefined) payload.state = updates.state;
        if (updates.pincode !== undefined) payload.pincode = updates.pincode;
        if (updates.amenities !== undefined) payload.amenities = Array.isArray(updates.amenities) ? updates.amenities.join(',') : updates.amenities;

        const response = await api.put(`/accommodations/${id}`, payload);
        const acc = response.data;
        return {
            ...acc,
            ownerId: acc.owner_id,
            imageUrl: acc.image_url,
            images: acc.images,
            contactPhone: acc.contact_phone,
            amenities: Array.isArray(acc.amenities)
                ? acc.amenities
                : (typeof acc.amenities === 'string' ? acc.amenities.split(',') : []),
            status: acc.status,
            isVerified: acc.is_verified
        };
    },


    submitAccommodationPayment: async (id: string): Promise<void> => {
        await api.put(`/accommodations/${id}/submit-payment`);
    },

    verifyEntity: async (id: string, type: 'room' | 'accommodation') => {
        const endpoint = type === 'room' ? `/reading-rooms/${id}/verify` : `/accommodations/${id}/verify`;
        const response = await api.put(endpoint);
        return response.data;
    },

    rejectEntity: async (id: string, type: 'room' | 'accommodation', reason: string) => {
        // Since we don't have a specific backend endpoint for rejection with reason in this stub,
        // we'll simulate it or use a generic update if available.
        // For now, assuming a similar endpoint structure for rejection.
        // If the backend doesn't exist, this will 404, but per instructions we implement the frontend logic.
        // Ideally: POST /reading-rooms/{id}/reject { reason }
        const endpoint = type === 'room' ? `/reading-rooms/${id}/reject` : `/accommodations/${id}/reject`;
        const response = await api.put(endpoint, { reason });
        return response.data;
    }
};
