/**
 * Universal responsive image — renders a <picture> with AVIF → WebP → JPEG
 * sources and a width-descriptor srcset. The browser picks the best format
 * + size for its current layout slot.
 *
 *   <ResponsiveImage
 *      source="listings/abc/photo.jpg"
 *      widths={IMAGE_PRESETS.hero}
 *      sizes="(min-width: 1024px) 768px, 100vw"
 *      alt="Hero photo of ABC Reading Room"
 *      priority      // = LCP, no lazy-load
 *   />
 *
 * `priority` flips loading="eager" + fetchpriority="high" and skips lazy
 * decoding. Use it for the single most-important image on each page.
 */
import React from 'react';
import { imageUrl, imageSrcSet, IMAGE_PRESETS } from '../utils/imageUtils';

export interface ResponsiveImageProps {
    source: string;
    widths?: readonly number[];
    sizes?: string;
    alt: string;
    priority?: boolean;
    /** Layout dimensions for CLS — both required when known. */
    width?: number;
    height?: number;
    className?: string;
    style?: React.CSSProperties;
    /** Background colour shown before the image decodes. */
    backgroundColor?: string;
}

export const ResponsiveImage: React.FC<ResponsiveImageProps> = ({
    source,
    widths = IMAGE_PRESETS.card,
    sizes = '(min-width: 1024px) 50vw, 100vw',
    alt,
    priority = false,
    width,
    height,
    className,
    style,
    backgroundColor = '#f3f4f6',
}) => {
    if (!source) {
        // No image at all — render a neutral placeholder slot so layout
        // doesn't shift later if the URL arrives.
        return (
            <div
                className={className}
                style={{
                    backgroundColor,
                    width: width ? `${width}px` : '100%',
                    aspectRatio: width && height ? `${width}/${height}` : '4/3',
                    ...style,
                }}
                aria-label={alt}
            />
        );
    }

    const widthsArr = [...widths];
    const fallbackWidth = widthsArr[Math.floor(widthsArr.length / 2)] ?? 800;

    return (
        <picture>
            <source
                type="image/avif"
                srcSet={imageSrcSet(source, widthsArr, 'avif')}
                sizes={sizes}
            />
            <source
                type="image/webp"
                srcSet={imageSrcSet(source, widthsArr, 'webp')}
                sizes={sizes}
            />
            <img
                src={imageUrl(source, { w: fallbackWidth, fmt: 'jpg' })}
                srcSet={imageSrcSet(source, widthsArr, 'jpg')}
                sizes={sizes}
                alt={alt}
                width={width}
                height={height}
                loading={priority ? 'eager' : 'lazy'}
                // fetchpriority isn't in React's stock JSX types yet — cast through.
                {...({ fetchpriority: priority ? 'high' : 'auto' } as Record<string, string>)}
                decoding="async"
                className={className}
                style={{
                    backgroundColor,
                    display: 'block',
                    width: '100%',
                    height: 'auto',
                    ...style,
                }}
            />
        </picture>
    );
};

export default ResponsiveImage;
