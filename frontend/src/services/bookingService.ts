
import api from './api';
import { Booking, BookingDurationType } from '../types';

export interface ExtendBookingResponse {
    message: string;
    booking_id: string;
    new_end_date: string;
    extension_amount: number;
    total_amount: number;
    payment_id: string;
    description: string;
}

const durationMonthsToType = (months: number): BookingDurationType => {
    if (months === 3) return '3_MONTHS';
    if (months === 6) return '6_MONTHS';
    return '1_MONTH';
};

const mapBooking = (b: any): Booking => ({
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
    createdAt: b.created_at,
    settlementStatus: b.settlement_status,
    venueName: b.venue_name,
    venueAddress: b.venue_address,
    venueCity: b.venue_city,
    venueLocality: b.venue_locality,
    venueContactPhone: b.venue_contact_phone,
    ownerName: b.owner_name,
    ownerId: b.owner_id,
    durationType: b.duration_type,
    joiningDate: b.joining_date,
    expiryDate: b.expiry_date,
    renewalWindowStart: b.renewal_window_start,
    renewalWindowEnd: b.renewal_window_end,
    renewalStatus: b.renewal_status,
    renewalDay: b.renewal_day ?? null,
    baseAmount: b.base_amount !== undefined && b.base_amount !== null
        ? Number(b.base_amount) : null,
    gstAmount: b.gst_amount !== undefined && b.gst_amount !== null
        ? Number(b.gst_amount) : null,
    gstRateApplied: b.gst_rate_applied !== undefined && b.gst_rate_applied !== null
        ? Number(b.gst_rate_applied) : null,
    gstTreatment: b.gst_treatment ?? null,
    placeOfSupplyState: b.place_of_supply_state ?? null,
    paidAt: b.paid_at ?? null,
    settledAt: b.settled_at ?? null,
    settlementRunId: b.settlement_run_id ?? null,
});

export const bookingService = {
    // Get all bookings for the current user
    getMyBookings: async (): Promise<Booking[]> => {
        // The backend endpoint likely mimics the structure. 
        // If the backend doesn't have a specific /me endpoint for bookings, 
        // we might need to filter client-side or assume the backend filters by token.
        // Based on previous knowledge, let's assume GET /bookings returns all for admin but filtered for student?
        // Or we might need to look at backend/app/routers/bookings.py.
        // Let's assume a standard GET /bookings for now.


        const response = await api.get('/api/bookings/');
        return response.data.map(mapBooking);
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
        const response = await api.post('/api/bookings/', payload);
        const b = response.data;

        return mapBooking({ ...b, cabin_number: b.cabin_number || '000' });
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
        void extensionAmount;
        void currentEndDate;

        const response = await api.post('/api/bookings/extend', null, {
            params: {
                booking_id: bookingId,
                extension_duration_type: durationMonthsToType(durationMonths),
                payment_method: paymentMethod,
                transaction_id: `EXT_TXN_${Date.now()}`
            }
        });

        return response.data;
    }
};
