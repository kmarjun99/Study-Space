import React, { useState, useEffect } from 'react';
import { Heart } from 'lucide-react';
import { favoritesService } from '../services/favoritesService';
import { toast } from 'react-hot-toast';

interface FavoriteButtonProps {
  accommodationId?: string;
  readingRoomId?: string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export const FavoriteButton: React.FC<FavoriteButtonProps> = ({
  accommodationId,
  readingRoomId,
  size = 'md',
  showLabel = false
}) => {
  const [isFavorited, setIsFavorited] = useState(false);
  const [favoriteId, setFavoriteId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const sizeClasses = {
    sm: 'h-5 w-5',
    md: 'h-6 w-6',
    lg: 'h-8 w-8'
  };

  const buttonSizeClasses = {
    sm: 'p-1.5',
    md: 'p-2',
    lg: 'p-3'
  };

  useEffect(() => {
    checkFavoriteStatus();
  }, [accommodationId, readingRoomId]);

  const checkFavoriteStatus = async () => {
    // Check if user is logged in
    const token = localStorage.getItem('studySpace_token');
    if (!token) {
      // User not logged in - don't check favorite status
      return;
    }

    try {
      const result = await favoritesService.checkFavorite(accommodationId, readingRoomId);
      setIsFavorited(result.is_favorited);
      setFavoriteId(result.favorite_id);
    } catch (error) {
      // Silent fail - user not logged in or other error
      console.error('Error checking favorite status:', error);
    }
  };

  const handleToggleFavorite = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // Check if user is logged in
    const token = localStorage.getItem('studySpace_token');
    if (!token) {
      toast.error('Please login to add favorites');
      return;
    }

    if (isLoading) return;

    setIsLoading(true);
    try {
      if (isFavorited && favoriteId) {
        // Remove from favorites
        await favoritesService.removeFavorite(favoriteId);
        setIsFavorited(false);
        setFavoriteId(null);
        toast.success('Removed from favorites');
        window.dispatchEvent(new CustomEvent('favoritesChanged'));
      } else {
        // Add to favorites
        const result = await favoritesService.addFavorite(accommodationId, readingRoomId);
        setIsFavorited(true);
        setFavoriteId(result.id);
        toast.success('Added to favorites');
        window.dispatchEvent(new CustomEvent('favoritesChanged'));
      }
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to update favorites';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button
      onClick={handleToggleFavorite}
      disabled={isLoading}
      className={`${buttonSizeClasses[size]} rounded-full transition-all duration-200 ${
        isFavorited
          ? 'bg-red-100 hover:bg-red-200 text-red-600'
          : 'bg-gray-100 hover:bg-gray-200 text-gray-600'
      } ${isLoading ? 'opacity-50 cursor-wait' : ''} ${
        showLabel ? 'flex items-center gap-2 px-4' : ''
      }`}
      title={isFavorited ? 'Remove from favorites' : 'Add to favorites'}
    >
      <Heart
        className={`${sizeClasses[size]} transition-all ${
          isFavorited ? 'fill-current' : ''
        } ${isLoading ? 'animate-pulse' : ''}`}
      />
      {showLabel && (
        <span className="text-sm font-medium">
          {isFavorited ? 'Saved' : 'Save'}
        </span>
      )}
    </button>
  );
};
