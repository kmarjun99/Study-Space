import api from './api';
import { Ad, TargetAudience, AdCategoryEntity } from '../types';

export interface AdCreatePayload {
  title: string;
  description: string;
  image_url: string;
  cta_text: string;
  link: string;
  category_id?: string;
  target_audience: TargetAudience;
  is_active?: boolean;
  start_date?: string;
  end_date?: string;
}

export interface AdUpdatePayload {
  title?: string;
  description?: string;
  image_url?: string;
  cta_text?: string;
  link?: string;
  category_id?: string;
  target_audience?: TargetAudience;
  is_active?: boolean;
  start_date?: string;
  end_date?: string;
}

export const adService = {
  // Get all ad categories (Dynamic from backend with Fallback)
  getCategories: async (): Promise<AdCategoryEntity[]> => {
    try {
      const response = await api.get('/ad-categories/');
      if (response.data && response.data.length > 0) {
        return response.data;
      }
    } catch (e) {
      console.warn("Failed to fetch categories, using fallback:", e);
    }

    // Fallback Categories (if backend fails or is empty)
    return [
      {
        id: 'cat_student_deals',
        name: 'Student Deals',
        group: 'Student',
        description: 'Discounts on books, stationary, etc.',
        slug: 'student-deals',
        applicable_to: ['STUDENT'],
        status: 'ACTIVE',
        display_order: '1',
        created_at: new Date().toISOString()
      },
      {
        id: 'cat_food_beverage',
        name: 'Food & Beverage',
        group: 'Student',
        description: 'Cafes, fast food, and dining.',
        slug: 'food-beverage',
        applicable_to: ['STUDENT'],
        status: 'ACTIVE',
        display_order: '2',
        created_at: new Date().toISOString()
      },
      {
        id: 'cat_events',
        name: 'Events & Parties',
        group: 'Student',
        description: 'College fests, concerts, and meetups.',
        slug: 'events-parties',
        applicable_to: ['STUDENT'],
        status: 'ACTIVE',
        display_order: '3',
        created_at: new Date().toISOString()
      },
      {
        id: 'cat_hostels',
        name: 'Hostels & PGs',
        group: 'Housing',
        description: 'Accommodation listings.',
        slug: 'hostels-pgs',
        applicable_to: ['ALL'],
        status: 'ACTIVE',
        display_order: '4',
        created_at: new Date().toISOString()
      },
      {
        id: 'cat_apartments',
        name: 'Apartments for Rent',
        group: 'Housing',
        description: 'Full flats and apartments.',
        slug: 'apartments',
        applicable_to: ['ALL'],
        status: 'ACTIVE',
        display_order: '5',
        created_at: new Date().toISOString()
      },
      {
        id: 'cat_internships',
        name: 'Internships',
        group: 'Business',
        description: 'Internship opportunities.',
        slug: 'internships',
        applicable_to: ['STUDENT'],
        status: 'ACTIVE',
        display_order: '6',
        created_at: new Date().toISOString()
      },
      {
        id: 'cat_courses',
        name: 'Courses & Workshops',
        group: 'Business',
        description: 'Skill development courses.',
        slug: 'courses-workshops',
        applicable_to: ['STUDENT'],
        status: 'ACTIVE',
        display_order: '7',
        created_at: new Date().toISOString()
      },
      {
        id: 'cat_technology',
        name: 'Electronics & Tech',
        group: 'Other',
        description: 'Gadgets and software.',
        slug: 'electronics-tech',
        applicable_to: ['ALL'],
        status: 'ACTIVE',
        display_order: '8',
        created_at: new Date().toISOString()
      }
    ];
  },

  // Get all ads (for admin, include inactive)
  getAllAds: async (includeInactive = false): Promise<Ad[]> => {
    const response = await api.get('/ads/', {
      params: { include_inactive: includeInactive }
    });
    return response.data.map((ad: any) => ({
      id: ad.id,
      title: ad.title,
      description: ad.description,
      imageUrl: ad.image_url,
      ctaText: ad.cta_text,
      link: ad.link,
      categoryId: ad.category_id,
      targetAudience: ad.target_audience,
      isActive: ad.is_active,
      createdAt: ad.created_at,
      startDate: ad.start_date,
      endDate: ad.end_date,
      impressionCount: ad.impression_count || 0,
      clickCount: ad.click_count || 0,
    }));
  },

  // Get single ad
  getAd: async (adId: string): Promise<Ad> => {
    const response = await api.get(`/ads/${adId}`);
    const ad = response.data;
    return {
      id: ad.id,
      title: ad.title,
      description: ad.description,
      imageUrl: ad.image_url,
      ctaText: ad.cta_text,
      link: ad.link,
      categoryId: ad.category_id,
      targetAudience: ad.target_audience,
      isActive: ad.is_active,
      createdAt: ad.created_at,
      startDate: ad.start_date,
      endDate: ad.end_date,
      impressionCount: ad.impression_count || 0,
      clickCount: ad.click_count || 0,
    };
  },

  // Create new ad (accepts frontend camelCase Ad format, converts to snake_case)
  createAd: async (ad: Partial<Ad>): Promise<Ad> => {
    const payload = {
      title: ad.title,
      description: ad.description,
      image_url: ad.imageUrl,
      cta_text: ad.ctaText,
      link: ad.link,
      category_id: ad.categoryId,
      target_audience: ad.targetAudience,
      is_active: ad.isActive ?? true,
      start_date: ad.startDate,
      end_date: ad.endDate,
    };
    const response = await api.post('/ads/', payload);
    return response.data;
  },

  // Update ad
  updateAd: async (adId: string, payload: AdUpdatePayload): Promise<Ad> => {
    const response = await api.put(`/ads/${adId}`, payload);
    return response.data;
  },

  // Toggle ad active status
  toggleAd: async (adId: string): Promise<{ id: string; is_active: boolean }> => {
    const response = await api.patch(`/ads/${adId}/toggle`);
    return response.data;
  },

  // Track impression
  trackImpression: async (adId: string): Promise<void> => {
    await api.post(`/ads/${adId}/impression`);
  },

  // Track click
  trackClick: async (adId: string): Promise<void> => {
    await api.post(`/ads/${adId}/click`);
  },

  // Delete ad
  deleteAd: async (adId: string): Promise<void> => {
    await api.delete(`/ads/${adId}`);
  },

  // Legacy method name for backward compatibility
  getAds: async (): Promise<Ad[]> => {
    return adService.getAllAds(false);
  },
};

// Standalone function for targeting ads (used in StudentDashboard, ReadingRoomDetail, BookCabin)
export const getTargetedAd = (
  ads: Ad[],
  userRole: string,
  hasActiveBooking: boolean,
  placement: string
): Ad | null => {
  if (!ads || ads.length === 0) return null;

  const role = (userRole || '').toUpperCase();

  // Filter by audience
  const targetedAds = ads.filter(ad => {
    if (ad.targetAudience === 'ALL') return true;
    if (ad.targetAudience === 'STUDENT' && role === 'STUDENT') return true;
    if (ad.targetAudience === 'ADMIN' && (role === 'ADMIN' || role === 'OWNER')) return true;
    return false;
  });

  if (targetedAds.length === 0) return null;

  // Return random ad from filtered list
  return targetedAds[Math.floor(Math.random() * targetedAds.length)];
};
