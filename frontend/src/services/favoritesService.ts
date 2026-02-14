import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
  private getAuthHeader() {
    const token = localStorage.getItem('studySpace_token');
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
    return {};
  }

  async addFavorite(accommodationId?: string, readingRoomId?: string): Promise<Favorite> {
    const response = await axios.post(
      `${API_BASE_URL}/favorites/`,
      {
        accommodation_id: accommodationId || null,
        reading_room_id: readingRoomId || null
      },
      { headers: this.getAuthHeader() }
    );
    return response.data;
  }

  async getFavorites(): Promise<Favorite[]> {
    const response = await axios.get(
      `${API_BASE_URL}/favorites/`,
      { headers: this.getAuthHeader() }
    );
    return response.data;
  }

  async removeFavorite(favoriteId: string): Promise<void> {
    await axios.delete(
      `${API_BASE_URL}/favorites/${favoriteId}`,
      { headers: this.getAuthHeader() }
    );
  }

  async checkFavorite(accommodationId?: string, readingRoomId?: string): Promise<{
    is_favorited: boolean;
    favorite_id: string | null;
  }> {
    const params = new URLSearchParams();
    if (accommodationId) params.append('accommodation_id', accommodationId);
    if (readingRoomId) params.append('reading_room_id', readingRoomId);

    const response = await axios.get(
      `${API_BASE_URL}/favorites/check?${params}`,
      { headers: this.getAuthHeader() }
    );
    return response.data;
  }
}

export const favoritesService = new FavoritesService();
