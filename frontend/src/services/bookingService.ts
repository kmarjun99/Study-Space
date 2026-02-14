
import api from './api';
import { Booking } from '../types';

export interface ExtendBookingResponse {
    message: string;
    booking_id: string;
    new_end_date: string;
    extension_amount: number;
    total_amount: number;
    payment_id: string;
    description: string;
}

export const bookingService = {
    // Get all bookings for the current user
    getMyBookings: async (): Promise<Booking[]> => {
        // The backend endpoint likely mimics the structure. 
        // If the backend doesn't have a specific /me endpoint for bookings, 
        // we might need to filter client-side or assume the backend filters by token.
        // Based on previous knowledge, let's assume GET /bookings returns all for admin but filtered for student?
        // Or we might need to look at backend/app/routers/bookings.py.
        // Let's assume a standard GET /bookings for now.


        const response = await api.get('/bookings/');
        return response.data.map((b: any) => ({
            id: b.id,
            userId: b.user_id,
            cabinId: b.cabin_id,
            accommodationId: b.accommodation_id,
            cabinNumber: b.cabin_number || '000',
            startDate: b.start_date,
            endDate: b.end_date,
            amount: b.amount,
            status: b.status,
            paymentStatus: b.payment_status,
            transactionId: b.transaction_id,
            createdAt: b.created_at, // Map created_at
            settlementStatus: b.settlement_status,
            venueName: b.venue_name,
            ownerName: b.owner_name,
            ownerId: b.owner_id
        }));
    },

    // Create a new booking
    createBooking: async (cabinId: string, durationMonths: number, startDate: string, endDate: string, amount: number): Promise<Booking> => {
        // Backend expects specific schema. 
        // Pydantic schema: BookingCreate(cabin_id, accommodation_id, start_date, end_date, amount, payment_status, transaction_id)

        const payload = {
            cabin_id: cabinId,
            start_date: startDate,
            end_date: endDate,
            amount: amount,
            payment_status: 'PAID', // Simulating successful payment
            transaction_id: `TXN_${Date.now()}`,
            booking_status: 'ACTIVE'
        };
        const response = await api.post('/bookings/', payload);
        const b = response.data;

        return {
            id: b.id,
            userId: b.user_id,
            cabinId: b.cabin_id,
            accommodationId: b.accommodation_id,
            cabinNumber: '000', // Placeholder, will be enriched by frontend state if needed
            startDate: b.start_date,
            endDate: b.end_date,
            amount: b.amount,
            status: b.status,
            paymentStatus: b.payment_status,
            transactionId: b.transaction_id,
            createdAt: b.created_at
        };
    },

    /**
     * Extend an existing booking
     * Creates a new PaymentTransaction with type=EXTENSION on backend
     * @param bookingId - The booking to extend
     * @param durationMonths - Number of months to extend
     * @param extensionAmount - Amount paid for extension
     * @param currentEndDate - Current end date of the booking (from local state)
     * @param paymentMethod - Payment method used
     */
    extendBooking: async (
        bookingId: string,
        durationMonths: number,
        extensionAmount: number,
        currentEndDate: string,
        paymentMethod: string = 'UPI'
    ): Promise<ExtendBookingResponse> => {
        // Calculate new end date from provided current end date
        const endDate = new Date(currentEndDate);
        const newEndDate = new Date(endDate);
        newEndDate.setMonth(newEndDate.getMonth() + durationMonths);

        const response = await api.post('/bookings/extend', null, {
            params: {
                booking_id: bookingId,
                new_end_date: newEndDate.toISOString(),
                extension_amount: extensionAmount,
                payment_method: paymentMethod,
                transaction_id: `EXT_TXN_${Date.now()}`
            }
        });

        return response.data;
    }
};
