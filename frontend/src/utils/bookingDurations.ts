/**
 * Booking Duration Utilities
 * Handles duration types, price calculations, date calculations, and formatting
 */

import { BookingDurationType, DurationOption } from '../types';

/**
 * Configuration for all available booking durations
 */
export const DURATION_CONFIGS: Record<BookingDurationType, DurationOption> = {
  '1_DAY': { 
    type: '1_DAY', 
    label: '1 Day', 
    days: 1 
  },
  '1_WEEK': { 
    type: '1_WEEK', 
    label: '1 Week', 
    days: 7 
  },
  '1_MONTH': { 
    type: '1_MONTH', 
    label: '1 Month', 
    days: 30 
  },
  '3_MONTHS': { 
    type: '3_MONTHS', 
    label: '3 Months', 
    days: 90 
  },
  '6_MONTHS': { 
    type: '6_MONTHS', 
    label: '6 Months', 
    days: 180 
  },
};

/**
 * All available duration types
 */
export const ALL_DURATION_TYPES: BookingDurationType[] = [
  '1_DAY',
  '1_WEEK',
  '1_MONTH',
  '3_MONTHS',
  '6_MONTHS',
];

/**
 * Calculate end date based on start date and duration type
 */
export const calculateEndDate = (
  startDate: Date, 
  durationType: BookingDurationType
): Date => {
  const endDate = new Date(startDate);
  
  switch (durationType) {
    case '1_DAY':
      endDate.setDate(endDate.getDate() + 1);
      break;
      
    case '1_WEEK':
      endDate.setDate(endDate.getDate() + 7);
      break;
      
    case '1_MONTH':
      endDate.setMonth(endDate.getMonth() + 1);
      break;
      
    case '3_MONTHS':
      endDate.setMonth(endDate.getMonth() + 3);
      break;
      
    case '6_MONTHS':
      endDate.setMonth(endDate.getMonth() + 6);
      break;
      
    default:
      // Default to 1 month
      endDate.setMonth(endDate.getMonth() + 1);
  }
  
  return endDate;
};

/**
 * Format duration type as human-readable label
 */
export const formatDurationLabel = (durationType: BookingDurationType): string => {
  return DURATION_CONFIGS[durationType]?.label || durationType;
};

/**
 * Get duration configuration
 */
export const getDurationConfig = (durationType: BookingDurationType): DurationOption => {
  return DURATION_CONFIGS[durationType] || DURATION_CONFIGS['1_MONTH'];
};

/**
 * Validate if duration type is valid
 */
export const isValidDurationType = (durationType: string): durationType is BookingDurationType => {
  return ALL_DURATION_TYPES.includes(durationType as BookingDurationType);
};

/**
 * Get duration in days
 */
export const getDurationDays = (durationType: BookingDurationType): number => {
  return DURATION_CONFIGS[durationType]?.days || 30;
};

/**
 * Parse duration price from venue configuration
 * Returns the custom price set by owner, or fallback for 1_MONTH
 */
export const getDurationPrice = (
  durationPrices: { [key: string]: number | null } | undefined,
  durationType: BookingDurationType,
  fallbackPrice?: number
): number | null => {
  if (!durationPrices) {
    // No price config - use fallback for 1_MONTH
    return (durationType === '1_MONTH' && fallbackPrice) ? fallbackPrice : null;
  }
  
  const price = durationPrices[durationType];
  
  // If price is set, use it
  if (price !== null && price !== undefined) {
    return price;
  }
  
  // No price set - use fallback for 1_MONTH
  if (durationType === '1_MONTH' && fallbackPrice) {
    return fallbackPrice;
  }
  
  return null;
};

/**
 * Check if a duration is enabled for a venue
 */
export const isDurationEnabled = (
  allowedDurations: BookingDurationType[] | undefined,
  durationType: BookingDurationType
): boolean => {
  if (!allowedDurations || allowedDurations.length === 0) {
    // Default: only monthly if not configured
    return durationType === '1_MONTH';
  }
  return allowedDurations.includes(durationType);
};

/**
 * Get available durations for a venue
 * Returns only durations that are both allowed and have prices set
 */
export const getAvailableDurations = (
  allowedDurations: BookingDurationType[] | undefined,
  durationPrices: { [key: string]: number | null } | undefined,
  fallbackPrice?: number
): BookingDurationType[] => {
  // Default to 1_MONTH if nothing configured
  const allowed = allowedDurations && allowedDurations.length > 0 
    ? allowedDurations 
    : ['1_MONTH'] as BookingDurationType[];
  
  // If no duration prices configured at all, but we have a fallback price (venue.priceStart)
  // then allow 1_MONTH with the base price
  const hasPriceConfig = durationPrices && Object.keys(durationPrices).some(key => {
    const val = durationPrices[key];
    return val !== null && val !== undefined && val > 0;
  });
  
  if (!hasPriceConfig && fallbackPrice && fallbackPrice > 0) {
    // Use base price as 1_MONTH default
    return allowed.includes('1_MONTH') ? ['1_MONTH'] : [];
  }
  
  // Filter to only durations with valid prices
  return allowed.filter(duration => {
    const price = getDurationPrice(durationPrices, duration, fallbackPrice);
    return price !== null && price > 0;
  });
};

/**
 * Format price for display
 */
export const formatPrice = (price: number): string => {
  return `₹${price.toLocaleString('en-IN')}`;
};

/**
 * Check if venue has flexible duration pricing configured
 */
export const hasFlexibleDurations = (
  allowedDurations: BookingDurationType[] | undefined
): boolean => {
  if (!allowedDurations || allowedDurations.length === 0) return false;
  
  // Has flexible durations if it offers more than just monthly
  return allowedDurations.length > 1 || 
         (allowedDurations.length === 1 && allowedDurations[0] !== '1_MONTH');
};

/**
 * Get default duration for a venue
 */
export const getDefaultDuration = (
  allowedDurations: BookingDurationType[] | undefined
): BookingDurationType => {
  const available = allowedDurations || ['1_MONTH'];
  
  // Prefer 1_MONTH if available, otherwise use first available
  if (available.includes('1_MONTH')) {
    return '1_MONTH';
  }
  
  return available[0] || '1_MONTH';
};
