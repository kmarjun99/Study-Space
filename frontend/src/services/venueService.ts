
import api from './api';
import { ReadingRoom, Cabin } from '../types';

export const venueService = {

    getAllReadingRooms: async (): Promise<ReadingRoom[]> => {
        const response = await api.get('/reading-rooms/');
        // Safety check
        if (!response.data || !Array.isArray(response.data)) {
            console.warn("getAllReadingRooms returned invalid data:", response.data);
            return [];
        }

        return response.data.map((room: any) => ({
            ...room,
            imageUrl: room.image_url,
            images: room.images, // Now correctly parsed by backend if needed, or we trust it
            ownerId: room.owner_id,
            priceStart: room.price_start,
            contactPhone: room.contact_phone,
            amenities: room.amenities || [], // Backend returns list now
            city: room.city,
            area: room.area,
            locality: room.locality,
            state: room.state,
            pincode: room.pincode,
            latitude: room.latitude,
            longitude: room.longitude,
            status: room.status,
            isVerified: room.is_verified
        }));
    },

    getMyReadingRooms: async (): Promise<ReadingRoom[]> => {
        const response = await api.get('/reading-rooms/my-venues');
        if (!response.data || !Array.isArray(response.data)) {
            console.warn("getMyReadingRooms returned invalid data:", response.data);
            return [];
        }

        return response.data.map((room: any) => ({
            ...room,
            imageUrl: room.image_url,
            images: room.images,
            ownerId: room.owner_id,
            priceStart: room.price_start,
            contactPhone: room.contact_phone,
            amenities: room.amenities || [],
            status: room.status,
            isVerified: room.is_verified
        }));
    },

    deleteReadingRoom: async (roomId: string): Promise<void> => {
        await api.delete(`/reading-rooms/${roomId}`);
    },

    getReadingRoomById: async (roomId: string): Promise<ReadingRoom> => {
        const response = await api.get(`/reading-rooms/${roomId}`);
        const room = response.data;
        return {
            ...room,
            imageUrl: room.image_url,
            images: room.images,
            ownerId: room.owner_id,
            priceStart: room.price_start,
            contactPhone: room.contact_phone,
            amenities: room.amenities || [],
            status: room.status,
            isVerified: room.is_verified
        };
    },

    getAllCabins: async (): Promise<Cabin[]> => {
        const response = await api.get('/cabins/');
        // Safety check: if response.data is null or undefined, return empty array
        if (!response.data || !Array.isArray(response.data)) {
            console.warn("getAllCabins returned invalid data:", response.data);
            return [];
        }

        return response.data.map((cabin: any) => ({
            ...cabin,
            readingRoomId: cabin.reading_room_id,
            amenities: cabin.amenities || [],
        }));
    },


    createReadingRoom: async (data: Partial<ReadingRoom>): Promise<ReadingRoom> => {
        const payload: any = {
            name: data.name,
            address: data.address,
            description: data.description,
            image_url: data.imageUrl,
            images: data.images, // Expecting JSON string already or List (Backend handles both)
            amenities: data.amenities, // Send as List
            contact_phone: data.contactPhone,
            price_start: data.priceStart,
            city: data.city,
            area: data.area,
            locality: data.locality,
            state: data.state,
            pincode: data.pincode,
            latitude: data.latitude,
            longitude: data.longitude
        };

        const response = await api.post('/reading-rooms/', payload);
        const room = response.data;
        return {
            ...room,
            imageUrl: room.image_url,
            images: room.images,
            ownerId: room.owner_id,
            priceStart: room.price_start,
            contactPhone: room.contact_phone,
            amenities: room.amenities || [],
            status: room.status,
            isVerified: room.is_verified
        };
    },

    updateReadingRoom: async (id: string, updates: Partial<ReadingRoom>): Promise<ReadingRoom> => {
        // Backend expects snake_case, frontend uses camelCase.
        const payload: any = {};
        if (updates.name !== undefined) payload.name = updates.name;
        if (updates.address !== undefined) payload.address = updates.address;
        if (updates.city !== undefined) payload.city = updates.city;
        if (updates.area !== undefined) payload.area = updates.area;
        if (updates.locality !== undefined) payload.locality = updates.locality;
        if (updates.state !== undefined) payload.state = updates.state;
        if (updates.pincode !== undefined) payload.pincode = updates.pincode;
        if (updates.description !== undefined) payload.description = updates.description;
        if (updates.imageUrl !== undefined) payload.image_url = updates.imageUrl;
        if (updates.images !== undefined) payload.images = updates.images;
        if (updates.contactPhone !== undefined) payload.contact_phone = updates.contactPhone;
        if (updates.priceStart !== undefined) payload.price_start = updates.priceStart;
        if (updates.latitude !== undefined) payload.latitude = updates.latitude;
        if (updates.longitude !== undefined) payload.longitude = updates.longitude;
        if (updates.amenities !== undefined) {
            payload.amenities = updates.amenities; // Send as List
        }

        const response = await api.put(`/reading-rooms/${id}`, payload);
        const room = response.data;
        return {
            ...room,
            imageUrl: room.image_url,
            images: room.images,
            ownerId: room.owner_id,
            priceStart: room.price_start,
            contactPhone: room.contact_phone,
            amenities: room.amenities || [],
            status: room.status,
            isVerified: room.is_verified
        };
    },

    submitVenuePayment: async (id: string): Promise<void> => {
        await api.put(`/reading-rooms/${id}/submit-payment`);
    },

    verifyVenue: async (id: string): Promise<ReadingRoom> => {
        const response = await api.put(`/reading-rooms/${id}/verify`);
        const room = response.data;
        return {
            ...room,
            imageUrl: room.image_url,
            images: room.images,
            ownerId: room.owner_id,
            priceStart: room.price_start,
            contactPhone: room.contact_phone,
            amenities: room.amenities || [],
            status: room.status,
            isVerified: room.is_verified
        };
    },


    getMyStudents: async (): Promise<any[]> => {
        const response = await api.get('/reading-rooms/my-students');
        // Map snake_case to camelCase
        return response.data.map((u: any) => ({
            id: u.id,
            email: u.email,
            name: u.name,
            role: u.role,
            avatarUrl: u.avatar_url,
            phone: u.phone,
            currentLat: u.current_lat,
            currentLong: u.current_long
        }));
    },

    createCabin: async (readingRoomId: string, data: Partial<Cabin>): Promise<Cabin> => {
        const payload = {
            reading_room_id: readingRoomId,
            number: data.number,
            floor: data.floor,
            price: data.price,
            status: data.status || 'AVAILABLE',
            amenities: data.amenities, // Send List
            zone: data.zone,
            row_label: data.rowLabel
        };
        const response = await api.post(`/reading-rooms/${readingRoomId}/cabins`, payload);
        const cabin = response.data;
        return {
            ...cabin,
            readingRoomId: cabin.reading_room_id,
            amenities: cabin.amenities || [],
        };
    },

    updateCabin: async (cabinId: string, data: Partial<Cabin>): Promise<Cabin> => {
        const payload = {
            ...data,
            amenities: data.amenities // Send List
        };
        const response = await api.put(`/cabins/${cabinId}`, payload);
        const cabin = response.data;
        return {
            ...cabin,
            readingRoomId: cabin.reading_room_id,
            amenities: cabin.amenities || [],
        };
    },

    createCabinsBulk: async (readingRoomId: string, cabinsData: Partial<Cabin>[]): Promise<Cabin[]> => {
        // Run in parallel
        const promises = cabinsData.map(data => venueService.createCabin(readingRoomId, data));
        return Promise.all(promises);
    },


    deleteCabins: async (cabinIds: string[]): Promise<void> => {
        await api.post('/cabins/bulk-delete', { cabin_ids: cabinIds });
    },

    // Bulk update all cabin prices for a venue
    updateCabinsPrices: async (cabinIds: string[], newPrice: number): Promise<void> => {
        // Update each cabin's price in parallel
        const promises = cabinIds.map(id =>
            api.put(`/cabins/${id}`, { price: newPrice })
        );
        await Promise.all(promises);
    },

    checkReviewStatus: async (readingRoomId?: string, accommodationId?: string): Promise<boolean> => {
        const params: any = {};
        if (readingRoomId) params.reading_room_id = readingRoomId;
        if (accommodationId) params.accommodation_id = accommodationId;

        const response = await api.get('/reviews/status', { params });
        return response.data.hasReviewed;
    },

    submitReview: async (review: { readingRoomId?: string, accommodationId?: string, rating: number, comment: string }): Promise<void> => {
        const payload = {
            reading_room_id: review.readingRoomId,
            accommodation_id: review.accommodationId,
            rating: review.rating,
            comment: review.comment
        };
        // console.log("Submitting review payload:", payload);
        await api.post('/reviews/', payload);
    },

    getMyReviews: async (userId: string): Promise<any[]> => {
        const response = await api.get('/reviews/', { params: { user_id: userId } });
        return response.data;
    }
};
