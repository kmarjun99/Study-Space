/**
 * Public read-only API for SEO-indexed pages.
 *
 * Wraps the FastAPI /public/* surface. No auth. Designed for prerender —
 * every method is a plain async function with no client state.
 */
import api from './api';

export const CATEGORIES = [
    'reading-rooms',
    'study-cabins',
    'private-cabins',
    'shared-cabins',
    'pgs',
    'hostels',
    'co-working-spaces',
    'co-learning-spaces',
    'rental-houses',
    'rooms-for-rent',
] as const;

export type Category = (typeof CATEGORIES)[number];

export const CATEGORY_LABELS: Record<Category, string> = {
    'reading-rooms': 'Reading Rooms',
    'study-cabins': 'Study Cabins',
    'private-cabins': 'Private Cabins',
    'shared-cabins': 'Shared Cabins',
    'pgs': 'PGs',
    'hostels': 'Hostels',
    'co-working-spaces': 'Co-working Spaces',
    'co-learning-spaces': 'Co-learning Spaces',
    'rental-houses': 'Rental Houses',
    'rooms-for-rent': 'Rooms for Rent',
};

export const CATEGORY_SINGULAR: Record<Category, string> = {
    'reading-rooms': 'Reading Room',
    'study-cabins': 'Study Cabin',
    'private-cabins': 'Private Cabin',
    'shared-cabins': 'Shared Cabin',
    'pgs': 'PG',
    'hostels': 'Hostel',
    'co-working-spaces': 'Co-working Space',
    'co-learning-spaces': 'Co-learning Space',
    'rental-houses': 'Rental House',
    'rooms-for-rent': 'Room for Rent',
};

export type LocationKind = 'country' | 'state' | 'city' | 'locality' | 'landmark';

export interface PublicLocation {
    id: string;
    kind: LocationKind;
    slug: string;
    name: string;
    aliases: string[];
    parent_id: string | null;
    country_code: string;
    state_code: string | null;
    lat: number | null;
    lng: number | null;
    population_tier: number | null;
    has_inventory: boolean;
    listing_counts: Record<string, number>;
    metadata: Record<string, unknown>;
}

export interface Breadcrumb {
    kind: LocationKind;
    slug: string;
    name: string;
    state_code: string | null;
}

export interface LocationResponse {
    location: PublicLocation;
    breadcrumbs: Breadcrumb[];
    children: PublicLocation[];
}

export interface PublicListing {
    id: string;
    slug: string | null;
    name: string;
    description?: string | null;
    address?: string | null;
    city?: string | null;
    area?: string | null;
    locality?: string | null;
    state?: string | null;
    pincode?: string | null;
    lat?: number | null;
    lng?: number | null;
    images?: string | null;
    amenities?: string | null;
    price_start?: number | null;
    is_sponsored?: boolean;
}

export interface ListingsResponse {
    category: Category;
    count: number;
    listings: PublicListing[];
}

export interface ListingDetailResponse {
    category: Category;
    listing: PublicListing;
}

export const publicService = {
    async getCategories(): Promise<{ categories: { slug: Category; total_live: number }[] }> {
        return (await api.get('/api/public/categories')).data;
    },

    async getLocation(kind: LocationKind, slug: string): Promise<LocationResponse> {
        return (await api.get(`/api/public/locations/${kind}/${slug}`)).data;
    },

    async listListings(
        category: Category,
        opts?: { citySlug?: string; localitySlug?: string; limit?: number; offset?: number },
    ): Promise<ListingsResponse> {
        const params: Record<string, string | number> = { category };
        if (opts?.citySlug) params.city_slug = opts.citySlug;
        if (opts?.localitySlug) params.locality_slug = opts.localitySlug;
        if (opts?.limit) params.limit = opts.limit;
        if (opts?.offset) params.offset = opts.offset;
        return (await api.get('/api/public/listings', { params })).data;
    },

    async getListing(category: Category, slug: string): Promise<ListingDetailResponse> {
        return (await api.get(`/api/public/listings/${category}/by-slug/${slug}`)).data;
    },
};

// Helper guarded against typos in route params.
export function isKnownCategory(value: string): value is Category {
    return (CATEGORIES as readonly string[]).includes(value);
}
