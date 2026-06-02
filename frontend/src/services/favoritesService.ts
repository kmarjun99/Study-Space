// favoritesService talks to the backend /favorites/ router. It uses the
// shared `api` axios client (configured in ./api.ts) so the Authorization
// header + base URL behaviour stay consistent with every other service.
//
// In dev:  api.baseURL = http://localhost:8000  →  http://localhost:8000/favorites/...
// In prod: api.baseURL = ''                     →  /favorites/... (relative;
//          frontend nginx proxies /favorites/ to the backend Cloud Run service).
//
// The previous implementation imported axios directly and hardcoded
// `import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'`. Because the
// production frontend build INTENTIONALLY omits VITE_API_BASE_URL (relying on
// same-origin nginx proxy), the fallback fired and the prod owner portal hit
// http://localhost:8000/favorites/ → ERR_CONNECTION_REFUSED.
import api from './api';

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

class FavoritesService {
  async addFavorite(accommodationId?: string, readingRoomId?: string): Promise<Favorite> {
    const response = await api.post<Favorite>('/favorites/', {
      accommodation_id: accommodationId || null,
      reading_room_id: readingRoomId || null,
    });
    return response.data;
  }

  async getFavorites(): Promise<Favorite[]> {
    const response = await api.get<Favorite[]>('/favorites/');
    // Defensive: if a misrouting ever returns HTML (SPA fallback) or an
    // error envelope instead of an array, render the empty state cleanly
    // instead of crashing every consumer that calls `.map(...)`.
    if (!Array.isArray(response.data)) {
      console.warn('[Favorites] getFavorites: backend returned non-array — empty result.');
      return [];
    }
    return response.data;
  }

  async removeFavorite(favoriteId: string): Promise<void> {
    await api.delete(`/favorites/${favoriteId}`);
  }

  async checkFavorite(accommodationId?: string, readingRoomId?: string): Promise<{
    is_favorited: boolean;
    favorite_id: string | null;
  }> {
    const params: Record<string, string> = {};
    if (accommodationId) params.accommodation_id = accommodationId;
    if (readingRoomId) params.reading_room_id = readingRoomId;
    const response = await api.get('/favorites/check', { params });
    return response.data;
  }
}

export const favoritesService = new FavoritesService();
