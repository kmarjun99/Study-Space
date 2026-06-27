import api from './api';
import { BookingDurationType } from '../types';

export type RenewalStatus = 'ACTIVE' | 'RENEWAL_DUE' | 'EXPIRED' | 'PAYMENT_PENDING';
export type OwnerPaymentStatus = 'PAID' | 'PENDING' | 'REFUNDED';

export interface OwnerOperationalAccessStatus {
  readingRoomId: string;
  readingRoomName?: string;
  canOperate: boolean;
  reasonCode?: string | null;
  message: string;
  missingRequirements: string[];
  listingStatus?: string | null;
  isVerified: boolean;
  trustStatus: string;
  planStatus: string;
  paidAccessExpiresAt?: string | null;
  freeAccessUntil?: string | null;
  adminBlocked: boolean;
}

export interface OwnerStudentRow {
  studentId: string;
  name: string;
  email: string;
  phone?: string;
  verificationStatus: string;
  mustSetPassword: boolean;
  bookingId?: string;
  cabinId?: string;
  cabinNumber?: string;
  readingRoomId?: string;
  readingRoomName?: string;
  joiningDate?: string;
  expiryDate?: string;
  renewalWindowStart?: string;
  renewalWindowEnd?: string;
  renewalStatus?: RenewalStatus;
  renewalDay?: number | null;
  paymentStatus?: OwnerPaymentStatus;
  bookingStatus?: string;
  amount?: number;
  durationType?: BookingDurationType;
  createdAt?: string;
}

export interface OwnerStudentAssignmentInput {
  name: string;
  email: string;
  phone?: string;
  readingRoomId: string;
  cabinId: string;
  durationType: BookingDurationType;
  joiningDate: string;
  amount?: number;
  paymentStatus: OwnerPaymentStatus;
  paymentReference?: string;
  sendInvite?: boolean;
}

export interface OwnerBookingRenewInput {
  durationType?: BookingDurationType;
  amount?: number;
  paymentStatus: OwnerPaymentStatus;
  paymentReference?: string;
}

const mapRow = (row: any): OwnerStudentRow => ({
  studentId: row.student_id,
  name: row.name,
  email: row.email,
  phone: row.phone,
  verificationStatus: row.verification_status,
  mustSetPassword: Boolean(row.must_set_password),
  bookingId: row.booking_id,
  cabinId: row.cabin_id,
  cabinNumber: row.cabin_number,
  readingRoomId: row.reading_room_id,
  readingRoomName: row.reading_room_name,
  joiningDate: row.joining_date,
  expiryDate: row.expiry_date,
  renewalWindowStart: row.renewal_window_start,
  renewalWindowEnd: row.renewal_window_end,
  renewalStatus: row.renewal_status,
  renewalDay: row.renewal_day ?? null,
  paymentStatus: row.payment_status,
  bookingStatus: row.booking_status,
  amount: row.amount,
  durationType: row.duration_type,
  createdAt: row.created_at,
});

const mapAction = (response: any) => ({
  success: response.success,
  message: response.message,
  student: response.student ? mapRow(response.student) : undefined,
});

const mapAccess = (row: any): OwnerOperationalAccessStatus => ({
  readingRoomId: row.reading_room_id,
  readingRoomName: row.reading_room_name,
  canOperate: Boolean(row.can_operate),
  reasonCode: row.reason_code ?? null,
  message: row.message,
  missingRequirements: row.missing_requirements || [],
  listingStatus: row.listing_status,
  isVerified: Boolean(row.is_verified),
  trustStatus: row.trust_status || 'CLEAR',
  planStatus: row.plan_status || 'NONE',
  paidAccessExpiresAt: row.paid_access_expires_at ?? null,
  freeAccessUntil: row.free_access_until ?? null,
  adminBlocked: Boolean(row.admin_blocked),
});

export const ownerStudentService = {
  async accessStatus(): Promise<OwnerOperationalAccessStatus[]> {
    const response = await api.get('/api/owner/operational-access');
    return response.data.map(mapAccess);
  },

  async list(params?: { renewalStatus?: RenewalStatus | 'ALL'; paymentStatus?: OwnerPaymentStatus | 'ALL' }): Promise<OwnerStudentRow[]> {
    const response = await api.get('/api/owner/students', {
      params: {
        renewal_status: params?.renewalStatus && params.renewalStatus !== 'ALL' ? params.renewalStatus : undefined,
        payment_status: params?.paymentStatus && params.paymentStatus !== 'ALL' ? params.paymentStatus : undefined,
      },
    });
    return response.data.map(mapRow);
  },

  async create(input: OwnerStudentAssignmentInput) {
    const response = await api.post('/api/owner/students', {
      name: input.name,
      email: input.email,
      phone: input.phone || null,
      reading_room_id: input.readingRoomId,
      cabin_id: input.cabinId,
      duration_type: input.durationType,
      joining_date: input.joiningDate,
      amount: input.amount,
      payment_status: input.paymentStatus,
      payment_reference: input.paymentReference || null,
      send_invite: input.sendInvite ?? true,
    });
    return mapAction(response.data);
  },

  async renew(bookingId: string, input: OwnerBookingRenewInput) {
    const response = await api.post(`/api/owner/student-bookings/${bookingId}/renew`, {
      duration_type: input.durationType,
      amount: input.amount,
      payment_status: input.paymentStatus,
      payment_reference: input.paymentReference || null,
    });
    return mapAction(response.data);
  },

  async markPaid(bookingId: string, amount?: number, paymentReference?: string) {
    const response = await api.post(`/api/owner/student-bookings/${bookingId}/mark-paid`, {
      amount,
      payment_reference: paymentReference || null,
    });
    return mapAction(response.data);
  },

  async release(bookingId: string) {
    const response = await api.post(`/api/owner/student-bookings/${bookingId}/release`);
    return mapAction(response.data);
  },

  async resendInvite(studentId: string) {
    const response = await api.post(`/api/owner/students/${studentId}/resend-invite`);
    return mapAction(response.data);
  },
};
