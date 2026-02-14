import api from './api';
import { User } from '../types';

export const userService = {
    getAllUsers: async (): Promise<User[]> => {
        const response = await api.get('/users/');
        // Mapping backend response to frontend User type if strictly needed,
        // but typically they match. 
        // Backend UserResponse: id, email, name, role, avatar_url, phone
        // Frontend User: id, name, email, role, avatarUrl, phone...
        return response.data.map((u: any) => ({
            id: u.id,
            name: u.name,
            email: u.email,
            role: u.role,
            avatarUrl: u.avatar_url,
            phone: u.phone,
            verificationStatus: u.verification_status
        }));
    },

    getUserById: async (userId: string): Promise<User | null> => {
        try {
            const response = await api.get(`/users/${userId}`);
            const u = response.data;
            return {
                id: u.id,
                name: u.name,
                email: u.email,
                role: u.role,
                avatarUrl: u.avatar_url,
                phone: u.phone,
                verificationStatus: u.verification_status
            } as User;
        } catch (e) {
            console.error('Failed to fetch user:', e);
            return null;
        }
    },

    /**
     * Update user details (Super Admin only)
     */
    updateUser: async (userId: string, updates: Partial<User>): Promise<User> => {
        const payload: any = {};
        if (updates.name !== undefined) payload.name = updates.name;
        if (updates.email !== undefined) payload.email = updates.email;
        if (updates.role !== undefined) payload.role = updates.role;
        if (updates.avatarUrl !== undefined) payload.avatar_url = updates.avatarUrl;
        if (updates.phone !== undefined) payload.phone = updates.phone;
        if (updates.verificationStatus !== undefined) payload.verification_status = updates.verificationStatus;

        const response = await api.put(`/users/${userId}`, payload);
        const u = response.data;
        return {
            id: u.id,
            name: u.name,
            email: u.email,
            role: u.role,
            avatarUrl: u.avatar_url,
            phone: u.phone,
            verificationStatus: u.verification_status
        } as User;
    }
};
