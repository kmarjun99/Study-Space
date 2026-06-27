import { Booking } from '../types';

export type RenewalBadgeVariant = 'success' | 'warning' | 'error' | 'info';

export interface RenewalDisplay {
  label: string;
  variant: RenewalBadgeVariant;
  needsAttention: boolean;
}

export const getRenewalDisplay = (booking: Pick<Booking, 'renewalStatus' | 'paymentStatus'>): RenewalDisplay => {
  if (booking.renewalStatus === 'PAYMENT_PENDING' || booking.paymentStatus === 'PENDING') {
    return { label: 'Payment Pending', variant: 'warning', needsAttention: true };
  }
  if (booking.renewalStatus === 'RENEWAL_DUE') {
    return { label: 'Renewal Due', variant: 'warning', needsAttention: true };
  }
  if (booking.renewalStatus === 'EXPIRED') {
    return { label: 'Expired', variant: 'error', needsAttention: true };
  }
  return { label: 'Active', variant: 'success', needsAttention: false };
};

export const formatRenewalWindow = (
  start?: string,
  end?: string,
  locale = 'en-IN',
): string => {
  if (!start || !end) return '—';
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
    return '—';
  }
  const options: Intl.DateTimeFormatOptions = { day: '2-digit', month: 'short', year: 'numeric' };
  return `${startDate.toLocaleDateString(locale, options)} - ${endDate.toLocaleDateString(locale, options)}`;
};
