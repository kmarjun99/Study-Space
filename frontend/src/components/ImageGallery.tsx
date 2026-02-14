import React, { useState, useRef, useEffect } from 'react';
import { ChevronLeft, ChevronRight, X, ZoomIn, Maximize2, BadgeCheck, ImageOff } from 'lucide-react';

interface ImageGalleryProps {
    images: string[];
    isVerified?: boolean;
    venueName: string;
    className?: string;
}

const FALLBACK_IMAGE = 'https://images.unsplash.com/photo-1521587760476-6c12a4b040da?auto=format&fit=crop&q=80&w=800';

export const ImageGallery: React.FC<ImageGalleryProps> = ({
    images,
    isVerified = false,
    venueName,
    className = ''
}) => {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [touchStart, setTouchStart] = useState<number | null>(null);
    const [touchEnd, setTouchEnd] = useState<number | null>(null);
    const [imageErrors, setImageErrors] = useState<Set<number>>(new Set());
    const containerRef = useRef<HTMLDivElement>(null);

    // Use fallback if no images provided
    const displayImages = images.length > 0 ? images : [FALLBACK_IMAGE];
    const hasMultipleImages = displayImages.length > 1;

    // Handle keyboard navigation
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (isFullscreen) {
                if (e.key === 'Escape') setIsFullscreen(false);
                if (e.key === 'ArrowLeft') goToPrev();
                if (e.key === 'ArrowRight') goToNext();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isFullscreen, currentIndex]);

    const goToNext = () => {
        setCurrentIndex((prev) => (prev + 1) % displayImages.length);
    };

    const goToPrev = () => {
        setCurrentIndex((prev) => (prev - 1 + displayImages.length) % displayImages.length);
    };

    const goToIndex = (index: number) => {
        setCurrentIndex(index);
    };

    // Touch handlers for swipe
    const minSwipeDistance = 50;

    const onTouchStart = (e: React.TouchEvent) => {
        setTouchEnd(null);
        setTouchStart(e.targetTouches[0].clientX);
    };

    const onTouchMove = (e: React.TouchEvent) => {
        setTouchEnd(e.targetTouches[0].clientX);
    };

    const onTouchEnd = () => {
        if (!touchStart || !touchEnd) return;
        const distance = touchStart - touchEnd;
        const isLeftSwipe = distance > minSwipeDistance;
        const isRightSwipe = distance < -minSwipeDistance;

        if (isLeftSwipe) goToNext();
        if (isRightSwipe) goToPrev();
    };

    const handleImageError = (index: number) => {
        setImageErrors(prev => new Set(prev).add(index));
    };

    const getImageSrc = (index: number) => {
        if (imageErrors.has(index)) return FALLBACK_IMAGE;
        return displayImages[index];
    };

    return (
        <>
            {/* Main Gallery */}
            <div
                ref={containerRef}
                className={`relative rounded-2xl overflow-hidden bg-gray-900 ${className}`}
                onTouchStart={onTouchStart}
                onTouchMove={onTouchMove}
                onTouchEnd={onTouchEnd}
            >
                {/* Main Image */}
                <div className="relative aspect-[16/9] md:aspect-[21/9]">
                    <img
                        src={getImageSrc(currentIndex)}
                        alt={`${venueName} - Photo ${currentIndex + 1}`}
                        className="w-full h-full object-cover transition-opacity duration-300"
                        onError={() => handleImageError(currentIndex)}
                    />

                    {/* Gradient Overlay */}
                    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-black/20" />

                    {/* Verified Badge */}
                    {isVerified && (
                        <div className="absolute top-4 left-4 flex items-center gap-1.5 bg-white/95 backdrop-blur-sm px-3 py-1.5 rounded-full shadow-lg">
                            <BadgeCheck className="w-4 h-4 text-green-600" />
                            <span className="text-xs font-semibold text-gray-800">Verified Images</span>
                        </div>
                    )}

                    {/* No Images Badge */}
                    {images.length === 0 && (
                        <div className="absolute top-4 left-4 flex items-center gap-1.5 bg-amber-100/95 backdrop-blur-sm px-3 py-1.5 rounded-full shadow-lg">
                            <ImageOff className="w-4 h-4 text-amber-600" />
                            <span className="text-xs font-semibold text-amber-800">Sample Image</span>
                        </div>
                    )}

                    {/* Image Counter */}
                    <div className="absolute bottom-4 left-4 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-full">
                        <span className="text-white text-sm font-medium">
                            {currentIndex + 1} / {displayImages.length}
                        </span>
                    </div>

                    {/* Fullscreen Button */}
                    <button
                        onClick={() => setIsFullscreen(true)}
                        className="absolute bottom-4 right-4 bg-black/60 backdrop-blur-sm p-2.5 rounded-full hover:bg-black/80 transition-colors group"
                        title="View fullscreen"
                    >
                        <Maximize2 className="w-5 h-5 text-white group-hover:scale-110 transition-transform" />
                    </button>

                    {/* Navigation Arrows - Desktop */}
                    {hasMultipleImages && (
                        <>
                            <button
                                onClick={goToPrev}
                                className="absolute left-4 top-1/2 -translate-y-1/2 bg-white/90 backdrop-blur-sm p-2 rounded-full shadow-lg hover:bg-white transition-all opacity-0 md:opacity-100 hover:scale-110 group"
                            >
                                <ChevronLeft className="w-6 h-6 text-gray-800" />
                            </button>
                            <button
                                onClick={goToNext}
                                className="absolute right-4 top-1/2 -translate-y-1/2 bg-white/90 backdrop-blur-sm p-2 rounded-full shadow-lg hover:bg-white transition-all opacity-0 md:opacity-100 hover:scale-110 group"
                            >
                                <ChevronRight className="w-6 h-6 text-gray-800" />
                            </button>
                        </>
                    )}
                </div>

                {/* Thumbnail Strip */}
                {hasMultipleImages && (
                    <div className="absolute bottom-16 left-1/2 -translate-x-1/2 flex gap-2 p-2 bg-black/40 backdrop-blur-sm rounded-xl">
                        {displayImages.map((_, index) => (
                            <button
                                key={index}
                                onClick={() => goToIndex(index)}
                                className={`w-2.5 h-2.5 rounded-full transition-all ${index === currentIndex
                                        ? 'bg-white scale-125'
                                        : 'bg-white/50 hover:bg-white/80'
                                    }`}
                            />
                        ))}
                    </div>
                )}

                {/* Swipe Indicator - Mobile Only */}
                {hasMultipleImages && (
                    <div className="md:hidden absolute bottom-20 left-1/2 -translate-x-1/2 text-white/60 text-xs flex items-center gap-1">
                        <ChevronLeft className="w-3 h-3" />
                        <span>Swipe to explore</span>
                        <ChevronRight className="w-3 h-3" />
                    </div>
                )}
            </div>

            {/* Fullscreen Modal */}
            {isFullscreen && (
                <div
                    className="fixed inset-0 z-50 bg-black flex items-center justify-center"
                    onClick={() => setIsFullscreen(false)}
                >
                    {/* Close Button */}
                    <button
                        onClick={() => setIsFullscreen(false)}
                        className="absolute top-4 right-4 z-10 bg-white/10 hover:bg-white/20 p-3 rounded-full transition-colors"
                    >
                        <X className="w-6 h-6 text-white" />
                    </button>

                    {/* Image Counter */}
                    <div className="absolute top-4 left-4 z-10 bg-white/10 px-4 py-2 rounded-full">
                        <span className="text-white font-medium">
                            {currentIndex + 1} of {displayImages.length}
                        </span>
                    </div>

                    {/* Main Image */}
                    <img
                        src={getImageSrc(currentIndex)}
                        alt={`${venueName} - Photo ${currentIndex + 1}`}
                        className="max-w-full max-h-full object-contain"
                        onClick={(e) => e.stopPropagation()}
                        onError={() => handleImageError(currentIndex)}
                    />

                    {/* Navigation Arrows */}
                    {hasMultipleImages && (
                        <>
                            <button
                                onClick={(e) => { e.stopPropagation(); goToPrev(); }}
                                className="absolute left-4 top-1/2 -translate-y-1/2 bg-white/10 hover:bg-white/20 p-3 rounded-full transition-colors"
                            >
                                <ChevronLeft className="w-8 h-8 text-white" />
                            </button>
                            <button
                                onClick={(e) => { e.stopPropagation(); goToNext(); }}
                                className="absolute right-4 top-1/2 -translate-y-1/2 bg-white/10 hover:bg-white/20 p-3 rounded-full transition-colors"
                            >
                                <ChevronRight className="w-8 h-8 text-white" />
                            </button>
                        </>
                    )}

                    {/* Thumbnail Strip */}
                    {hasMultipleImages && (
                        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex gap-3">
                            {displayImages.map((img, index) => (
                                <button
                                    key={index}
                                    onClick={(e) => { e.stopPropagation(); goToIndex(index); }}
                                    className={`w-16 h-12 rounded-lg overflow-hidden border-2 transition-all ${index === currentIndex
                                            ? 'border-white scale-110'
                                            : 'border-transparent opacity-60 hover:opacity-100'
                                        }`}
                                >
                                    <img
                                        src={imageErrors.has(index) ? FALLBACK_IMAGE : img}
                                        alt={`Thumbnail ${index + 1}`}
                                        className="w-full h-full object-cover"
                                        onError={() => handleImageError(index)}
                                    />
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </>
    );
};

export default ImageGallery;
