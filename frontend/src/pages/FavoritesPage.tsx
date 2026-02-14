import React, { useState, useEffect } from 'react';
import { Heart, MapPin, IndianRupee, Trash2 } from 'lucide-react';
import { favoritesService, Favorite } from '../services/favoritesService';
import { Loading } from '../components/Loading';
import { toast } from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';

interface FavoritesPageProps {
  onFavoritesChange?: () => void;
}

export const FavoritesPage: React.FC<FavoritesPageProps> = ({ onFavoritesChange }) => {
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadFavorites();
  }, []);

  const loadFavorites = async () => {
    setIsLoading(true);
    try {
      const data = await favoritesService.getFavorites();
      setFavorites(data);
    } catch (error: any) {
      toast.error('Failed to load favorites');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRemove = async (favoriteId: string) => {
    try {
      await favoritesService.removeFavorite(favoriteId);
      setFavorites(favorites.filter(f => f.id !== favoriteId));
      toast.success('Removed from favorites');
      // Trigger sync
      window.dispatchEvent(new CustomEvent('favoritesChanged'));
      if (onFavoritesChange) {
        onFavoritesChange();
      }
    } catch (error) {
      toast.error('Failed to remove favorite');
    }
  };

  const handleViewDetails = (favorite: Favorite) => {
    if (favorite.item_type === 'accommodation' && favorite.accommodation_id) {
      navigate(`/student/accommodation/${favorite.accommodation_id}`);
    } else if (favorite.item_type === 'reading_room' && favorite.reading_room_id) {
      navigate(`/student/reading-room/${favorite.reading_room_id}`);
    }
  };

  if (isLoading) {
    return <Loading text="Loading your favorites..." />;
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Heart className="h-8 w-8 text-red-600 fill-current" />
        <h1 className="text-3xl font-bold text-gray-900">My Favorites</h1>
      </div>

      {favorites.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm p-12 text-center">
          <Heart className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-900 mb-2">
            No favorites yet
          </h3>
          <p className="text-gray-600 mb-6">
            Start exploring and save your favorite accommodations and reading rooms
          </p>
          <div className="flex gap-4 justify-center">
            <button
              onClick={() => navigate('/student/accommodation')}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Browse Accommodations
            </button>
            <button
              onClick={() => navigate('/student/book')}
              className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Browse Reading Rooms
            </button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-gray-600 mb-6">
            You have {favorites.length} saved {favorites.length === 1 ? 'item' : 'items'}
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {favorites.map((favorite) => (
              <div
                key={favorite.id}
                className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => handleViewDetails(favorite)}
              >
                {/* Image */}
                <div className="relative h-48 bg-gray-200">
                  {favorite.item_image ? (
                    <img
                      src={favorite.item_image}
                      alt={favorite.item_name || 'Property'}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gray-100">
                      <Heart className="h-16 w-16 text-gray-300" />
                    </div>
                  )}
                  
                  {/* Type Badge */}
                  <div className="absolute top-2 left-2">
                    <span className="px-3 py-1 bg-white bg-opacity-90 text-xs font-medium rounded-full">
                      {favorite.item_type === 'accommodation' ? 'Accommodation' : 'Reading Room'}
                    </span>
                  </div>

                  {/* Remove Button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemove(favorite.id);
                    }}
                    className="absolute top-2 right-2 p-2 bg-white bg-opacity-90 rounded-full hover:bg-red-50 hover:text-red-600 transition-colors"
                    title="Remove from favorites"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>

                {/* Content */}
                <div className="p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2 truncate">
                    {favorite.item_name || 'Unnamed'}
                  </h3>

                  {favorite.item_city && (
                    <div className="flex items-center gap-1 text-sm text-gray-600 mb-3">
                      <MapPin className="h-4 w-4" />
                      <span>{favorite.item_city}</span>
                    </div>
                  )}

                  {favorite.item_price !== null && (
                    <div className="flex items-center gap-1 text-lg font-bold text-blue-600">
                      <IndianRupee className="h-5 w-5" />
                      <span>{favorite.item_price.toLocaleString()}</span>
                      <span className="text-sm font-normal text-gray-600">
                        {favorite.item_type === 'accommodation' ? '/month' : '/day'}
                      </span>
                    </div>
                  )}

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleViewDetails(favorite);
                    }}
                    className="w-full mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    View Details
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
