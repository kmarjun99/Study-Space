
import React, { useState } from 'react';
import { Ad } from '../types';
import { ExternalLink, X, ChevronRight, Sparkles } from 'lucide-react';
import { Card, Button } from './UI';

// Default fallback placeholder for broken ad images
const AD_PLACEHOLDER_IMAGE = 'https://images.unsplash.com/photo-1557804506-669a67965ba0?auto=format&fit=crop&w=800&q=80';

interface AdBannerProps {
  ad: Ad | null;
  variant?: 'card' | 'banner' | 'modal';
  onClose?: () => void;
  className?: string;
}

export const AdBanner: React.FC<AdBannerProps> = ({ ad, variant = 'card', onClose, className = '' }) => {
  const [isVisible, setIsVisible] = useState(true);
  const [imageError, setImageError] = useState(false);

  if (!isVisible || !ad) return null;

  // Validate image URL exists and is not empty
  const hasValidImageUrl = ad.imageUrl && ad.imageUrl.trim() !== '';
  const displayImageUrl = imageError || !hasValidImageUrl ? AD_PLACEHOLDER_IMAGE : ad.imageUrl;

  const handleClose = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsVisible(false);
    if (onClose) onClose();
  };

  // Handle image load error - replace with placeholder
  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    console.warn(`Ad image failed to load: ${ad.imageUrl}`);
    setImageError(true);
    // Directly set the fallback src to prevent infinite loop
    const target = e.target as HTMLImageElement;
    target.onerror = null; // Prevent infinite loop if placeholder also fails
    target.src = AD_PLACEHOLDER_IMAGE;
  };

  // Navigate to ad link - handles both external and internal URLs
  const handleCtaClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!ad.link) return;

    console.log(`Ad CTA Clicked: ${ad.id} - ${ad.title} -> ${ad.link}`);

    // Check if external URL (starts with http/https) or internal route
    if (ad.link.startsWith('http://') || ad.link.startsWith('https://')) {
      // External link - open in new tab
      window.open(ad.link, '_blank', 'noopener,noreferrer');
    } else {
      // Internal link - navigate within app
      window.location.href = ad.link;
    }
  };

  // Track ad impression/click on container
  const handleAdClick = () => {
    console.log(`Ad Clicked: ${ad.id} - ${ad.title}`);
    // Track click event for analytics
    handleCtaClick({ stopPropagation: () => { } } as React.MouseEvent);
  };

  // ============================================================
  // BANNER VARIANT - Mobile: Compact inline, Desktop: Full banner
  // ============================================================
  if (variant === 'banner') {
    return (
      <>
        {/* MOBILE: Compact horizontal inline ad (visible < md) */}
        <div
          className={`md:hidden relative w-full overflow-hidden rounded-xl shadow-lg cursor-pointer ${className}`}
          onClick={handleAdClick}
        >
          <div className="flex items-stretch h-20">
            {/* Small image */}
            <div className="relative w-20 h-20 flex-shrink-0 overflow-hidden">
              <img
                src={displayImageUrl}
                alt={ad.title}
                className="w-full h-full object-cover"
                onError={handleImageError}
                loading="lazy"
              />
              <div className="absolute top-1 left-1">
                <span className="inline-flex items-center gap-0.5 text-[8px] font-semibold text-white bg-indigo-600/90 px-1.5 py-0.5 rounded-full">
                  <Sparkles className="w-2 h-2" />
                  Ad
                </span>
              </div>
            </div>

            {/* Compact content */}
            <div className="flex-1 bg-gradient-to-r from-gray-900 to-indigo-900 p-2.5 flex flex-col justify-center min-w-0">
              <h4 className="text-white font-bold text-sm leading-tight truncate">
                {ad.title}
              </h4>
              <p className="text-gray-400 text-[11px] line-clamp-1 mb-1.5">
                {ad.description}
              </p>
              <button
                className="self-start px-2.5 py-1 text-[10px] font-semibold bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-md flex items-center gap-1"
                onClick={handleCtaClick}
              >
                {ad.ctaText || 'View'}
                <ExternalLink className="w-2.5 h-2.5" />
              </button>
            </div>
          </div>
        </div>

        {/* DESKTOP: Full banner layout (visible >= md) */}
        <div
          className={`hidden md:block relative w-full overflow-hidden rounded-2xl shadow-xl cursor-pointer group ${className}`}
          onClick={handleAdClick}
        >
          <div className="flex flex-row">
            {/* Large Image Section */}
            <div className="relative w-2/5 min-h-[180px]">
              <img
                src={displayImageUrl}
                alt={ad.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                onError={handleImageError}
                loading="lazy"
              />
              <div className="absolute inset-0 bg-gradient-to-r from-transparent to-gray-900"></div>
              <div className="absolute top-3 left-3">
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-white bg-black/40 backdrop-blur-md px-2.5 py-1 rounded-full border border-white/20">
                  <Sparkles className="w-3 h-3" />
                  Sponsored
                </span>
              </div>
            </div>

            {/* Content Section */}
            <div className="flex-1 bg-gradient-to-br from-gray-900 via-gray-800 to-indigo-900 p-6 flex flex-col justify-center">
              <h4 className="text-white font-bold text-xl mb-2 leading-tight">
                {ad.title}
              </h4>
              <p className="text-gray-300 text-sm mb-5 line-clamp-3">
                {ad.description}
              </p>
              <Button
                className="w-auto min-h-[48px] px-6 py-3 text-base font-bold bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white border-none rounded-xl shadow-lg flex items-center justify-center gap-2"
                onClick={handleCtaClick}
              >
                {ad.ctaText || 'Learn More'}
                <ExternalLink className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </div>
      </>
    );
  }

  // ============================================================
  // CARD VARIANT - Mobile: Compact inline banner, Desktop: Full card
  // ============================================================
  return (
    <>
      {/* MOBILE VERSION - Compact horizontal layout (visible on sm and below) */}
      <Card className={`md:hidden overflow-hidden group cursor-pointer border-0 shadow-lg hover:shadow-xl transition-all duration-300 rounded-xl ${className}`}>
        <div className="flex items-stretch" onClick={handleAdClick}>
          {/* Small square image on left */}
          <div className="relative w-24 h-24 flex-shrink-0 overflow-hidden">
            <img
              src={displayImageUrl}
              alt={ad.title}
              className="w-full h-full object-cover"
              onError={handleImageError}
              loading="lazy"
            />
            {/* Sponsored badge - small */}
            <div className="absolute top-1 left-1">
              <span className="inline-flex items-center gap-0.5 text-[9px] font-semibold text-white bg-indigo-600/90 px-1.5 py-0.5 rounded-full">
                <Sparkles className="w-2 h-2" />
                Ad
              </span>
            </div>
          </div>

          {/* Content - compact */}
          <div className="flex-1 p-3 bg-gradient-to-r from-gray-900 to-indigo-900 flex flex-col justify-center min-w-0">
            <h4 className="text-white font-bold text-sm leading-tight truncate mb-1">
              {ad.title}
            </h4>
            <p className="text-gray-300 text-xs line-clamp-1 mb-2">
              {ad.description}
            </p>
            <button
              className="self-start px-3 py-1.5 text-xs font-semibold bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg flex items-center gap-1"
              onClick={handleCtaClick}
            >
              {ad.ctaText || 'View'}
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>

          {/* Close button */}
          {onClose && (
            <button
              onClick={handleClose}
              className="absolute top-1 right-1 p-1 bg-black/30 hover:bg-black/50 rounded-full text-white"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      </Card>

      {/* DESKTOP/TABLET VERSION - Full card layout (hidden on mobile) */}
      <Card className={`hidden md:block overflow-hidden group cursor-pointer border-0 shadow-lg hover:shadow-xl transition-all duration-300 rounded-2xl ${className}`}>
        {/* Large Image Section */}
        <div
          className="relative h-48 lg:h-52 overflow-hidden"
          onClick={handleAdClick}
        >
          <img
            src={displayImageUrl}
            alt={ad.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            onError={handleImageError}
            loading="lazy"
          />
          {/* Gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent"></div>

          {/* Sponsored badge */}
          <div className="absolute top-3 left-3">
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-white bg-indigo-600/90 backdrop-blur-md px-2.5 py-1 rounded-full shadow-md">
              <Sparkles className="w-3 h-3" />
              Sponsored
            </span>
          </div>

          {/* Title overlay on image */}
          <div className="absolute bottom-4 left-4 right-4">
            <h4 className="text-white font-bold text-xl lg:text-2xl leading-tight drop-shadow-lg">
              {ad.title}
            </h4>
          </div>

          {/* Close button */}
          {onClose && (
            <button
              onClick={handleClose}
              className="absolute top-3 right-3 p-2 bg-black/30 hover:bg-black/50 rounded-full text-white backdrop-blur-sm transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Content Section */}
        <div className="p-5 lg:p-6 bg-gradient-to-br from-indigo-50 to-white">
          <p className="text-gray-600 text-sm lg:text-base mb-5 line-clamp-2">
            {ad.description}
          </p>

          {/* CTA Button */}
          <Button
            className="w-full min-h-[48px] px-6 py-3 text-base font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white border-none rounded-xl shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2"
            onClick={handleCtaClick}
          >
            {ad.ctaText || 'Learn More'}
            <ChevronRight className="w-5 h-5" />
          </Button>
        </div>
      </Card>
    </>
  );
};
