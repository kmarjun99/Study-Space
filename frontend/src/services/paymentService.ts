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
        const response = await api.get<PaymentModesResponse>('/payments/user/payment-modes');
        return response.data;
    },

    /**
     * Get all refund requests for the current user
     */
    async getMyRefunds(): Promise<Refund[]> {
        const response = await api.get<Refund[]>('/payments/user/refunds');
        return response.data;
    },

    /**
     * Create a new refund request
     */
    async requestRefund(data: RefundRequestInput): Promise<Refund> {
        const response = await api.post<Refund>('/payments/refund/request', data);
        return response.data;
    },

    /**
     * Get all refund requests (Super Admin only)
     */
    async getAllRefunds(statusFilter?: string): Promise<RefundAdmin[]> {
        const params = statusFilter ? { status_filter: statusFilter } : {};
        const response = await api.get<RefundAdmin[]>('/payments/admin/refunds', { params });
        return response.data;
    },

    /**
     * Update refund status (Super Admin only)
     */
    async updateRefundStatus(refundId: string, status: string, adminNotes?: string): Promise<void> {
        await api.patch(`/payments/admin/refunds/${refundId}`, {
            status,
            admin_notes: adminNotes
        });
    },

    /**
     * Download PDF invoice for a booking.
     *
     * Retries once on transient gateway errors (502/503/504) because
     * Cloud Run cold-starts and brief container restarts surface as
     * those codes. Without a retry the user sees "Unable to generate
     * invoice" for what is actually a self-healing condition. Permanent
     * errors (400/401/403/404) are surfaced immediately with specific
     * messages — they require the user to do something, not wait.
     *
     * @param bookingId - The booking ID to generate invoice for
     * @returns Promise that resolves when download is complete
     * @throws Error if invoice generation fails (with a message tailored
     *               to the failure mode)
     */
    async downloadInvoice(bookingId: string): Promise<void> {
        const TRANSIENT_STATUSES = new Set([502, 503, 504]);

        const fetchOnce = async () => api.get(`/bookings/${bookingId}/invoice`, {
            responseType: 'blob',
            timeout: 60000, // 60 second timeout for PDF generation
        });

        let response;
        try {
            response = await fetchOnce();
        } catch (firstError: any) {
            // Retry exactly ONCE on transient gateway errors. A short delay
            // gives Cloud Run time to spin up if it scaled to zero.
            if (TRANSIENT_STATUSES.has(firstError?.response?.status)) {
                await new Promise(r => setTimeout(r, 1500));
                try {
                    response = await fetchOnce();
                } catch (secondError: any) {
                    throw new Error(
                        secondError?.response?.status === 502
                            ? 'Server is restarting. Please try again in a moment.'
                            : 'Server temporarily unavailable. Please try again.',
                    );
                }
            } else if (firstError.response?.status === 400) {
                throw new Error('Invoice can only be generated for paid bookings');
            } else if (firstError.response?.status === 401) {
                throw new Error('Session expired. Please refresh and sign in again.');
            } else if (firstError.response?.status === 403) {
                throw new Error('You can only download invoices for your own bookings');
            } else if (firstError.response?.status === 404) {
                throw new Error('Booking not found');
            } else {
                // Anything else (500, network failure, etc.) — generic but
                // mention the status code so support can diagnose quickly.
                const status = firstError?.response?.status;
                throw new Error(
                    status
                        ? `Unable to generate invoice (HTTP ${status}). Please try again.`
                        : 'Unable to reach server. Check your connection and try again.',
                );
            }
        }

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
    async createOrder(booking_id: string, amount: number, currency: string = 'INR'): Promise<{
        order_id: string;
        amount: number;
        currency: string;
        razorpay_key_id: string;
        is_demo?: boolean;
    }> {
        const response = await api.post('/razorpay/create-order', { 
            booking_id, 
            amount 
        });
        return response.data;
    },

    /**
     * Create Razorpay Order for Boost Request
     */
    async createBoostOrder(boost_request_id: string, amount: number, currency: string = 'INR'): Promise<{
        order_id: string;
        amount: number;
        currency: string;
        razorpay_key_id: string;
        is_demo?: boolean;
    }> {
        const response = await api.post('/razorpay/create-boost-order', { 
            boost_request_id, 
            amount 
        });
        return response.data;
    },

    /**
     * Create Razorpay Order for Venue Subscription
     */
    async createVenueOrder(data: {
        venue_id: string;
        venue_type: string;
        subscription_plan_id: string;
        amount: number;
    }): Promise<{
        order_id: string;
        amount: number;
        currency: string;
        razorpay_key_id: string;
        subscription_plan: any;
        is_demo?: boolean;
    }> {
        const response = await api.post('/payments/venue/create-order', data);
        return response.data;
    },

    /**
     * Verify Razorpay Payment  
     */
    async verifyPayment(data: {
        razorpay_order_id: string;
        razorpay_payment_id: string;
        razorpay_signature: string;
        booking_id?: string;  // Optional but should be provided for booking payments
    }): Promise<void> {
        await api.post('/razorpay/verify', data);
    },

    /**
     * Verify Venue Payment
     */
    async verifyVenuePayment(data: {
        razorpay_order_id: string;
        razorpay_payment_id: string;
        razorpay_signature: string;
        venue_id: string;
        venue_type: string;
        subscription_plan_id: string;
    }): Promise<void> {
        await api.post('/payments/venue/verify', data);
    }
};
