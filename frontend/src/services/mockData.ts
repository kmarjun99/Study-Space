
import { User, UserRole, Cabin, CabinStatus, Booking, Notification, ReadingRoom, Review, Accommodation, Gender, ListingStatus, SupportTicket, SubscriptionPlan, PromotionPlan, PromotionRequest } from '../types';

// ============================================
// ALL MOCK DATA CLEARED FOR PRODUCTION RESET
// Data now comes exclusively from backend APIs
// ============================================

// Empty arrays - Super Admin must create promotion plans
export const MOCK_PROMOTION_PLANS: PromotionPlan[] = [];
export const MOCK_PROMOTION_REQUESTS: PromotionRequest[] = [];

// Empty - Super Admin creates subscription plans
export const MOCK_PLANS: SubscriptionPlan[] = [];

// Empty - Support tickets come from backend
export const MOCK_TICKETS: SupportTicket[] = [];

// Empty - Users from auth system only
export const MOCK_USERS: User[] = [];

// Empty - Reading Rooms from backend only
export const MOCK_READING_ROOMS: ReadingRoom[] = [];

// Empty - Accommodations from backend only
export const MOCK_ACCOMMODATIONS: Accommodation[] = [];

// Empty cabins function - returns empty array
export function generateCabins(): Cabin[] {
  return [];
}

// Empty - Bookings from backend only
export const MOCK_BOOKINGS: Booking[] = [];

// Empty - Notifications from backend only
export const MOCK_NOTIFICATIONS: Notification[] = [];

// Empty - Reviews from backend only
export const MOCK_REVIEWS: Review[] = [];

// Cabins array for compatibility
export const MOCK_CABINS: Cabin[] = [];