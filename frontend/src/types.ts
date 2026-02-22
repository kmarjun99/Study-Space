
export enum UserRole {
  STUDENT = 'STUDENT',
  ADMIN = 'ADMIN',
  SUPER_ADMIN = 'SUPER_ADMIN',
}

export enum CabinStatus {
  AVAILABLE = 'AVAILABLE',
  OCCUPIED = 'OCCUPIED',
  MAINTENANCE = 'MAINTENANCE',
  RESERVED = 'RESERVED',
}

export enum PaymentMethod {
  UPI = 'UPI',
  CARD = 'CARD',
  WALLET = 'WALLET',
}

export enum Gender {
  MALE = 'MALE',
  FEMALE = 'FEMALE',
  UNISEX = 'UNISEX',
}


export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatarUrl?: string;
  phone?: string;
  verificationStatus?: 'PENDING' | 'VERIFIED' | 'REJECTED' | 'NOT_REQUIRED';
  has_active_waitlist?: boolean;
}


export enum ListingStatus {
  DRAFT = 'DRAFT',
  PAYMENT_PENDING = 'PAYMENT_PENDING',
  VERIFICATION_PENDING = 'VERIFICATION_PENDING',
  LIVE = 'LIVE',
  REJECTED = 'REJECTED',
  SUSPENDED = 'SUSPENDED',
}


// Location Master (for city search and autocomplete)
export interface Location {
  id: string;
  country: string;
  state: string;
  city: string;
  locality?: string;
  displayName: string;  // "Indiranagar, Bangalore"
  latitude?: number;
  longitude?: number;
}

export interface ReadingRoom {
  id: string;
  ownerId: string;
  name: string;
  address: string;
  city?: string;
  area?: string;
  locality?: string;
  state?: string;
  pincode?: string;
  latitude?: number;
  longitude?: number;
  locationId?: string;  // NEW: Reference to locations table
  description: string;
  imageUrl: string;
  images?: string; // JSON String representation of image array
  amenities: string[];
  contactPhone: string;
  priceStart: number;
  status: ListingStatus;
  isVerified?: boolean;
  isFeatured?: boolean;
  featuredPlan?: 'DAILY' | 'WEEKLY' | 'MONTHLY';
  featuredExpiry?: string;
  createdAt?: string; // Venue creation date
  // Payment & Subscription tracking
  subscriptionPlanId?: string;
  paymentId?: string;
  paymentDate?: string;
}

export interface Cabin {
  id: string;
  readingRoomId: string; // Link to the venue
  number: string;
  floor: number;
  amenities: string[];
  price: number;
  status: CabinStatus;
  currentOccupantId?: string; // null if available
  // Owner-defined seat positioning
  zone?: 'FRONT' | 'MIDDLE' | 'BACK';
  rowLabel?: string; // 'A', 'B', 'C', etc.
  // Temporary Hold System (BookMyShow-style)
  heldByUserId?: string;
  holdExpiresAt?: string;
}

export interface Accommodation {
  id: string;
  ownerId: string; // Linked to admin
  name: string;
  type: 'PG' | 'HOSTEL' | 'HOUSE';
  gender: Gender;
  address: string; // Acts as location
  city?: string;
  area?: string;
  locality?: string;
  state?: string;
  pincode?: string;
  locationId?: string;  // NEW: Reference to locations table
  latitude?: number;
  longitude?: number;
  price: number; // Monthly rent
  sharing: string; // e.g., "Single", "Double", "Triple"
  amenities: string[];
  imageUrl: string;
  images?: string; // JSON String
  contactPhone: string;

  rating: number;
  status: ListingStatus;
  isVerified?: boolean;
  isFeatured?: boolean;
  featuredPlan?: 'DAILY' | 'WEEKLY' | 'MONTHLY';
  featuredExpiry?: string;
}



export interface Booking {
  id: string;
  userId: string;
  cabinId: string;
  accommodationId?: string; // Added to support Housing Bookings
  cabinNumber: string;
  startDate: string;
  endDate: string;
  amount: number;
  status: 'ACTIVE' | 'EXPIRED' | 'CANCELLED' | 'HELD';
  paymentStatus: 'PAID' | 'PENDING' | 'REFUNDED';
  transactionId: string;
  createdAt: string; // Added to filter recent bookings
  // Enriched fields for Admin/Owner Console
  settlementStatus?: 'NOT_SETTLED' | 'SETTLED' | 'ON_HOLD';
  venueName?: string;
  ownerName?: string;
  ownerId?: string;
}

export interface Notification {
  id: string;
  userId: string; // Added to associate notification with specific user
  title: string;
  message: string;
  read: boolean;
  date: string;
  type: 'info' | 'success' | 'warning' | 'error';
  messageId?: string; // Link to message if notification is about a message
}

export interface Message {
  id: string;
  conversationId: string;
  senderId: string;
  senderName: string;
  senderRole: UserRole;
  receiverId: string;
  receiverName: string;
  receiverRole: UserRole;
  content: string;
  timestamp: string;
  read: boolean;
  venueId?: string; // Optional: link to specific venue
  venueName?: string; // Optional: venue name for context
  venueType?: 'reading_room' | 'accommodation'; // Optional: context type
}

export interface Conversation {
  id: string;
  participantIds: string[];
  participants: { id: string; name: string; role: UserRole; avatarUrl?: string }[];
  lastMessage?: Message;
  unreadCount: number;
  venueId?: string; // Optional: associate with specific venue
  venueName?: string;
  venueType?: 'reading_room' | 'accommodation';
}

export interface Review {
  id: string;
  userId: string;
  readingRoomId?: string;
  accommodationId?: string;
  rating: number; // 1 to 5
  comment: string;
  date: string;
}

// Legacy type for backward compatibility (deprecated)
export type AdCategoryLegacy = 'FOOD' | 'EDUCATION' | 'LIFESTYLE' | 'TRANSPORT';

// Dynamic Ad Category entity from backend
export interface AdCategoryEntity {
  id: string;
  name: string;
  slug: string;
  description?: string;
  icon?: string;
  group?: string;
  applicable_to: string[];
  status: 'ACTIVE' | 'INACTIVE';
  display_order: string;
  created_at: string;
}

export type TargetAudience = 'STUDENT' | 'ADMIN' | 'ALL';

export interface Ad {
  id: string;
  title: string;
  description: string;
  imageUrl: string;
  ctaText: string;
  link: string;
  categoryId?: string;  // References ad_categories.id
  category?: string;    // Legacy field for backward compatibility
  targetAudience: TargetAudience;
  // Campaign Management
  isActive?: boolean;
  createdAt?: string;
  startDate?: string;
  endDate?: string;
  // Analytics
  impressionCount?: number;
  clickCount?: number;
}

export type WaitlistStatus = 'ACTIVE' | 'NOTIFIED' | 'EXPIRED' | 'CANCELLED' | 'CONVERTED';

export interface WaitlistEntry {
  id: string;
  userId: string;
  cabinId: string; // Ensure this is mapped
  readingRoomId: string;
  ownerId?: string;
  status: WaitlistStatus;
  date: string; // created_at
  notifiedAt?: string;
  expiresAt?: string;
  priorityPosition?: number;
  // Enriched fields
  cabinNumber?: string;
  venueName?: string;
  venueAddress?: string;
  userName?: string;
  userEmail?: string;
}

export type TicketStatus = 'OPEN' | 'IN_PROGRESS' | 'WAITING_FOR_USER' | 'RESOLVED' | 'CLOSED';
export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
export type SupportCategory = 'BOOKING_ISSUE' | 'PAYMENT_ISSUE' | 'TECHNICAL_ISSUE' | 'GENERAL_HELP' | 'REFUND' | 'SUBSCRIPTION' | 'VENUE_ISSUE' | 'FEATURED_LISTING' | 'ACCOUNT' | 'CABIN_MANAGEMENT' | 'OTHER';

export interface SupportTicket {
  id: string;
  userId: string;
  userRole: UserRole;
  userEmail: string;
  userName: string;
  category: SupportCategory;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  createdAt: string;
  updatedAt: string;
  metaData?: {
    bookingId?: string;
    paymentId?: string;
    venueId?: string;
    deviceInfo?: string;
    appVersion?: string;
  };
  adminNotes?: string;
  adminResponse?: string;
}


export interface SubscriptionPlan {
  id: string;
  name: string;
  description: string;
  price: number;
  durationDays: number;
  features: string[];
  isActive: boolean;
  isDefault: boolean;
  createdBy: string;
  createdAt: string;
  billingCycle?: 'MONTHLY' | 'QUARTERLY' | 'YEARLY';
  allowedListingTypes?: string[];
  ctaLabel?: string;
}

// ============================================
// UNIFIED PROMOTION SYSTEM
// ============================================

// Promotion Plan - Created by Super Admin
export type PromotionPlanStatus = 'draft' | 'active' | 'inactive';
export type PromotionPlacement = 'FEATURED_SECTION' | 'TOP_LIST' | 'BANNER';
export type PromotionApplicableTo = 'READING_ROOM' | 'ACCOMMODATION' | 'BOTH';

export interface PromotionPlan {
  id: string;
  name: string;
  description: string;
  price: number;
  durationDays: number;
  applicableTo: PromotionApplicableTo;
  placement: PromotionPlacement;
  status: PromotionPlanStatus;
  createdBy: string;
  createdAt: string;
}

// Promotion Request - Created when Owner pays
export type PromotionRequestStatus =
  | 'initiated'
  | 'payment_pending'
  | 'paid'
  | 'admin_review'
  | 'approved'
  | 'rejected'
  | 'active'
  | 'expired';

export interface PromotionRequest {
  id: string;
  promotionPlanId: string;
  promotionPlanName: string;
  listingId: string;
  listingType: 'READING_ROOM' | 'ACCOMMODATION';
  listingName: string;
  ownerId: string;
  ownerName: string;
  ownerEmail: string;
  paymentId: string;
  price: number;
  durationDays: number;
  placement: PromotionPlacement;
  status: PromotionRequestStatus;
  requestedAt: string;
  approvedAt?: string;
  approvedBy?: string;
  expiryDate?: string;
  adminNotes?: string;
}

// Context State
export interface Favorite {
  id: string;
  user_id: string;
  accommodation_id: string | null;
  reading_room_id: string | null;
  created_at: string;
  item_name: string | null;
  item_type: 'accommodation' | 'reading_room' | null;
  item_image: string | null;
  item_price: number | null;
  item_city: string | null;
}

export interface AppState {
  favorites: Favorite[];
  currentUser: User | null;
  users: User[];
  readingRooms: ReadingRoom[];
  cabins: Cabin[];
  bookings: Booking[];
  notifications: Notification[];
  reviews: Review[];
  waitlist: WaitlistEntry[];
  accommodations: Accommodation[];
  tickets: SupportTicket[];
  settings: PlatformSettings;
  subscriptionPlans: SubscriptionPlan[];
  promotionPlans: PromotionPlan[];
  promotionRequests: PromotionRequest[];
  messages: Message[];
  conversations: Conversation[];
}

export interface PlatformSettings {
  platformName: string;
  supportEmail: string;
  supportPhone: string;
  maintenanceMode: boolean;
  features: {
    featuredListings: boolean;
    reviews: boolean;
    waitlist: boolean;
    newVenueRegistrations: boolean;
  };
  payments: {
    enableNewSubscriptions: boolean;
    featuredListingPrice: number;
    venueSubscriptionDurationDays: number;
  };
  locations: {
    cityBasedAvailability: boolean;
  };
  preferences: {
    landingPage: string;
    dateFormat: string;
    currency: string;
  };
}

export interface CityStats {
  name: string;
  is_active: boolean;
  total_venues: number;
  total_cabins: number;
  total_accommodations: number;
  active_bookings: number;
  occupancy_rate: number;
}

export interface AreaStats {
  name: string;
  venue_count: number;
  cabin_count: number;
}

export interface CityDetail extends CityStats {
  areas: AreaStats[];
  owners: string[];
}