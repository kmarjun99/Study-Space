/**
 * Payment Service
 * Handles API calls for Payment Modes and Refunds
 */

import api from './api';

// Types
export interface LastUsedPayment {
    method: string;
    gateway: string;
    reference: string | null;
    date: string;
}

export interface PaymentModesResponse {
    supported_methods: string[];
    last_used: LastUsedPayment | null;
}

export interface Refund {
    id: string;
    booking_id: string;
    venue_name: string;
    amount: number;
    reason: string;
    reason_text: string | null;
    status: 'REQUESTED' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED' | 'PROCESSED' | 'FAILED';
    requested_at: string;
    processed_at: string | null;
}

export interface RefundAdmin extends Refund {
    user_id: string;
    user_email: string;
    user_name: string;
    admin_notes: string | null;
    reviewed_by: string | null;
}

export interface RefundRequestInput {
    booking_id: string;
    reason: string;
    reason_text?: string;
}

// API Functions
export const paymentService = {
    /**
     * Get supported payment methods and last used payment for the user
     */
    async getPaymentModes(): Promise<PaymentModesResponse> {
        const response = await api.get<PaymentModesResponse>('/user/payment-modes');
        return response.data;
    },

    /**
     * Get all refund requests for the current user
     */
    async getMyRefunds(): Promise<Refund[]> {
        const response = await api.get<Refund[]>('/user/refunds');
        return response.data;
    },

    /**
     * Create a new refund request
     */
    async requestRefund(data: RefundRequestInput): Promise<Refund> {
        const response = await api.post<Refund>('/refund/request', data);
        return response.data;
    },

    /**
     * Get all refund requests (Super Admin only)
     */
    async getAllRefunds(statusFilter?: string): Promise<RefundAdmin[]> {
        const params = statusFilter ? { status_filter: statusFilter } : {};
        const response = await api.get<RefundAdmin[]>('/admin/refunds', { params });
        return response.data;
    },

    /**
     * Update refund status (Super Admin only)
     */
    async updateRefundStatus(refundId: string, status: string, adminNotes?: string): Promise<void> {
        await api.patch(`/admin/refunds/${refundId}`, {
            status,
            admin_notes: adminNotes
        });
    },

    /**
     * Download PDF invoice for a booking
     * @param bookingId - The booking ID to generate invoice for
     * @returns Promise that resolves when download is complete
     * @throws Error if invoice generation fails
     */
    async downloadInvoice(bookingId: string): Promise<void> {
        try {
            const response = await api.get(`/bookings/${bookingId}/invoice`, {
                responseType: 'blob',
                timeout: 60000 // 60 second timeout for PDF generation
            });

            // Create blob URL and trigger download
            const blob = new Blob([response.data], { type: 'application/pdf' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;

            // Extract filename from Content-Disposition header if available
            const contentDisposition = response.headers['content-disposition'];
            let filename = `Invoice_${bookingId.slice(0, 8)}.pdf`;
            if (contentDisposition) {
                const match = contentDisposition.match(/filename=(.+)/);
                if (match && match[1]) {
                    filename = match[1].replace(/['"]/g, '');
                }
            }

            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error: any) {
            if (error.response?.status === 400) {
                throw new Error('Invoice can only be generated for paid bookings');
            } else if (error.response?.status === 403) {
                throw new Error('You can only download invoices for your own bookings');
            } else if (error.response?.status === 404) {
                throw new Error('Booking not found');
            }
            throw new Error('Unable to generate invoice. Please try again later.');
        }
    },

    /**
     * Get all payment transactions for owner's venue (including extensions)
     */
    async getOwnerPaymentHistory(): Promise<{
        payments: Array<{
            id: string;
            booking_id: string;
            user_id: string;
            user_name: string;
            type: 'INITIAL' | 'EXTENSION' | 'REFUND';
            amount: number;
            date: string;
            venue_name: string;
            cabin_number: string;
            transaction_id: string;
            description: string;
            method: string;
        }>;
        total_count: number;
        total_amount: number;
    }> {
        const response = await api.get('/payments/owner/payment-history');
        return response.data;
    },

    /**
     * Create Razorpay Order
     */
    async createOrder(amount: number, currency: string = 'INR'): Promise<{
        id: string;
        amount: number;
        currency: string;
        key_id: string;
    }> {
        const response = await api.post('/payments/create-order', { amount, currency });
        return response.data;
    },

    /**
     * Verify Razorpay Payment
     */
    async verifyPayment(data: {
        razorpay_order_id: string;
        razorpay_payment_id: string;
        razorpay_signature: string;
        booking_id?: string;
    }): Promise<void> {
        await api.post('/payments/verify', data);
    }
};
