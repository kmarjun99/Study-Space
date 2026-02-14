
import api from './api';
import { UserRole } from '../types';

export const authService = {
    login: async (email: string, password: string) => {
        // Backend expects FormData for OAuth2 schema, usually sent as x-www-form-urlencoded
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const response = await api.post('/auth/login', formData, {
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        });
        return response.data; // Expected { access_token, token_type }
    },

    getCurrentUser: async () => {
        const response = await api.get('/auth/me');
        const u = response.data;
        return {
            id: u.id,
            name: u.name,
            email: u.email,
            role: u.role,
            avatarUrl: u.avatar_url,
            phone: u.phone
        };
    },

    register: async (email: string, password: string, role: string, name: string) => {
        const response = await api.post('/auth/register', {
            email,
            password,
            role,
            name
        });
        return response.data;
    },

    // OTP Methods
    sendOtp: async (email: string, phone: string | null, otpType: string) => {
        const response = await api.post('/otp/send', {
            email,
            phone,
            otp_type: otpType
        });
        return response.data;
    },

    verifyOtp: async (email: string, otpCode: string, otpType: string) => {
        const response = await api.post('/otp/verify', {
            email,
            otp_code: otpCode,
            otp_type: otpType
        });
        return response.data;
    },

    resendOtp: async (email: string, phone: string | null, otpType: string) => {
        const response = await api.post('/otp/resend', {
            email,
            phone,
            otp_type: otpType
        });
        return response.data;
    },

    // Password Reset Methods
    forgotPassword: async (email: string) => {
        const response = await api.post('/otp/forgot-password', {
            email
        });
        return response.data;
    },

    resetPassword: async (email: string, otpCode: string, newPassword: string) => {
        const response = await api.post('/otp/reset-password', {
            email,
            otp_code: otpCode,
            new_password: newPassword
        });
        return response.data;
    }
};
