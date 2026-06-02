import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Ad } from '../types';
import { AdBanner } from './AdBanner';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';

interface AdCarouselProps {
  ads: Ad[];
  variant?: 'card' | 'banner' | 'modal';
  autoSlideInterval?: number; // milliseconds
  className?: string;
}

const AdCarouselComponent: React.FC<AdCarouselProps> = ({
  ads,
  variant = 'banner',
  autoSlideInterval = 5000,
  className = ''
}) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [isClosed, setIsClosed] = useState(() => {
    // Check localStorage if user previously closed the ad
    const closedState = localStorage.getItem('adCarouselClosed');
    return closedState === 'true';
  });
  const touchStartX = useRef<number>(0);
  const touchEndX = useRef<number>(0);
  const resumeTimerRef = useRef<NodeJS.Timeout | null>(null);

  // IMPORTANT: Memoize validAds to prevent recreating on every render
  const validAds = useMemo(() => {
    return ads.filter(ad => ad !== null && ad !== undefined);
  }, [ads]);

  const adsCount = validAds.length;
  
  // Store adsCount in ref to use in effects without triggering re-runs
  const adsCountRef = useRef(adsCount);
  adsCountRef.current = adsCount;

  // Auto-slide effect - ONLY depend on isPaused and autoSlideInterval
  // IMPORTANT: This must be before any conditional returns (Rules of Hooks)
  useEffect(() => {
    if (isPaused || adsCountRef.current <= 1) return;

    const interval = setInterval(() => {
      setCurrentIndex((current) => {
        const count = adsCountRef.current;
        if (count <= 1) return current;
        return (current + 1) % count;
      });
    }, autoSlideInterval);

    return () => clearInterval(interval);
  }, [isPaused, autoSlideInterval]);

  // Cleanup resume timer on unmount
  useEffect(() => {
    return () => {
      if (resumeTimerRef.current) {
        clearTimeout(resumeTimerRef.current);
      }
    };
  }, []);

  const handleClose = useCallback(() => {
    setIsClosed(true);
    localStorage.setItem('adCarouselClosed', 'true');
  }, []);

  const goToSlide = useCallback((index: number) => {
    setCurrentIndex(index);
  }, []);

  const goToPrevious = useCallback(() => {
    setCurrentIndex((current) => {
      const count = adsCountRef.current;
      return current === 0 ? count - 1 : current - 1;
    });
  }, []);

  const goToNext = useCallback(() => {
    setCurrentIndex((current) => {
      const count = adsCountRef.current;
      return (current + 1) % count;
    });
  }, []);

  // If no ads, return null (after all hooks)
  if (adsCount === 0) return null;

  // If user closed the carousel, don't show it
  if (isClosed) return null;

  // If only one ad, show it without carousel controls (after all hooks)
  if (adsCount === 1) {
    return (
      <div className="relative">
        <AdBanner ad={validAds[0]} variant={variant} className={className} />
        <button
          onClick={handleClose}
          className="absolute top-3 right-3 bg-white/90 hover:bg-white text-gray-700 rounded-full p-1.5 shadow-lg z-20 transition-all hover:scale-110"
          aria-label="Close ad"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  // Touch handlers for swipe
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    touchEndX.current = e.touches[0].clientX; // Reset end position
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    touchEndX.current = e.touches[0].clientX;
  };

  const handleTouchEnd = () => {
    const swipeThreshold = 50; // minimum distance for swipe
    const diff = touchStartX.current - touchEndX.current;

    if (Math.abs(diff) > swipeThreshold) {
      // User did a swipe - handle navigation
      if (diff > 0) {
        // Swipe left - next slide
        goToNext();
      } else {
        // Swipe right - previous slide
        goToPrevious();
      }
      
      // Pause briefly after swipe so user can see the new ad
      setIsPaused(true);
      if (resumeTimerRef.current) {
        clearTimeout(resumeTimerRef.current);
      }
      resumeTimerRef.current = setTimeout(() => {
        setIsPaused(false);
      }, 3000); // Resume after 3 seconds
    }
    // If no swipe detected, don't pause - let auto-slide continue
  };

  // Safeguard: ensure currentIndex is always valid
  const safeIndex = currentIndex >= adsCount ? 0 : currentIndex;

  return (
    <div
      className={`relative group ${className}`}
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Carousel Container with Slide Animation */}
      <div className="relative overflow-hidden rounded-2xl">
        <div
          className="flex transition-transform duration-500 ease-out"
          style={{
            transform: `translateX(-${safeIndex * 100}%)`
          }}
        >
          {validAds.map((ad, index) => (
            <div key={ad.id || index} className="w-full flex-shrink-0">
              <AdBanner ad={ad} variant={variant} />
            </div>
          ))}
        </div>
      </div>

      {/* Navigation Arrows - Hidden on mobile, visible on desktop hover */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          goToPrevious();
        }}
        className="hidden md:flex absolute left-2 top-1/2 -translate-y-1/2 bg-white/90 hover:bg-white text-gray-800 rounded-full p-2 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-10"
        aria-label="Previous ad"
      >
        <ChevronLeft className="w-5 h-5" />
      </button>

      <button
        onClick={(e) => {
          e.stopPropagation();
          goToNext();
        }}
        className="hidden md:flex absolute right-2 top-1/2 -translate-y-1/2 bg-white/90 hover:bg-white text-gray-800 rounded-full p-2 shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-10"
        aria-label="Next ad"
      >
        <ChevronRight className="w-5 h-5" />
      </button>

      {/* Close Button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          handleClose();
        }}
        className="absolute top-3 right-3 bg-white/90 hover:bg-white text-gray-700 rounded-full p-1.5 shadow-lg z-20 transition-all hover:scale-110 opacity-70 hover:opacity-100"
        aria-label="Close ad"
      >
        <X className="w-4 h-4" />
      </button>

      {/* Dot Indicators */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-2 z-10">
        {validAds.map((_, index) => (
          <button
            key={index}
            onClick={(e) => {
              e.stopPropagation();
              goToSlide(index);
            }}
            className={`transition-all duration-300 rounded-full ${
              index === safeIndex
                ? 'w-6 h-2 bg-white'
                : 'w-2 h-2 bg-white/50 hover:bg-white/75'
            }`}
            aria-label={`Go to slide ${index + 1}`}
          />
        ))}
      </div>

      {/* Progress Bar (optional - shows auto-slide progress) */}
      {!isPaused && (
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-white/20 overflow-hidden">
          <div
            className="h-full bg-white/60 transition-all"
            style={{
              animation: `slideProgress ${autoSlideInterval}ms linear infinite`,
            }}
          />
        </div>
      )}

      <style>{`
        @keyframes slideProgress {
          from {
            width: 0%;
          }
          to {
            width: 100%;
          }
        }
      `}</style>
    </div>
  );
};
// Export memoized version to prevent unnecessary re-renders
export const AdCarousel = React.memo(AdCarouselComponent, (prevProps, nextProps) => {
  // Only re-render if ads actually changed (compare IDs)
  if (prevProps.variant !== nextProps.variant) return false;
  if (prevProps.autoSlideInterval !== nextProps.autoSlideInterval) return false;
  if (prevProps.className !== nextProps.className) return false;
  
  if (prevProps.ads.length !== nextProps.ads.length) return false;
  
  // Compare ad IDs
  for (let i = 0; i < prevProps.ads.length; i++) {
    if (prevProps.ads[i]?.id !== nextProps.ads[i]?.id) return false;
  }
  
  return true; // Props haven't changed, skip re-render
});