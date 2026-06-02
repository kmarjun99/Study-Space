/**
 * Public listing detail page — `/listing/:category/:slug`.
 *
 * Renders every signal Google + AI crawlers want:
 *   - LocalBusiness / LodgingBusiness JSON-LD (depending on category)
 *   - BreadcrumbList
 *   - FAQPage (auto-generated from listing attributes)
 *   - Open Graph image + canonical
 *
 * Conversion paths kept above the fold: contact owner CTA + check-availability
 * link (deep-links into the authenticated app for booking).
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin, CheckCircle2, ChevronLeft, ExternalLink } from 'lucide-react';
import { SEO } from '../../seo/SEO';
import ResponsiveImage from '../../components/ResponsiveImage';
import { IMAGE_PRESETS } from '../../utils/imageUtils';
import {
    breadcrumbList, faqPage, localBusiness, SITE_ORIGIN,
    type LocalBusinessKind,
} from '../../seo/schema';
import {
    Category, CATEGORY_LABELS, CATEGORY_SINGULAR,
    isKnownCategory, PublicListing, publicService,
} from '../../services/publicService';


// Which schema.org sub-type best fits each category.
const SCHEMA_KIND: Record<Category, LocalBusinessKind> = {
    'reading-rooms': 'LocalBusiness',
    'study-cabins': 'LocalBusiness',
    'private-cabins': 'LocalBusiness',
    'shared-cabins': 'LocalBusiness',
    'pgs': 'LodgingBusiness',
    'hostels': 'Hostel',
    'co-working-spaces': 'LocalBusiness',
    'co-learning-spaces': 'LocalBusiness',
    'rental-houses': 'Apartment',
    'rooms-for-rent': 'Residence',
};


function generateFAQs(args: { listing: PublicListing; category: Category }): { question: string; answer: string }[] {
    const { listing, category } = args;
    const place = [listing.locality, listing.city].filter(Boolean).join(', ');
    const singular = CATEGORY_SINGULAR[category];
    return [
        {
            question: `Where is ${listing.name} located?`,
            answer: place
                ? `${listing.name} is located in ${place}. ${listing.address || ''}`.trim()
                : (listing.address || 'Address details are available on the listing page.'),
        },
        listing.price_start != null && {
            question: `What does ${listing.name} cost?`,
            answer: `Pricing starts at ₹${listing.price_start.toLocaleString('en-IN')}/month. Final pricing depends on the seat type and duration you choose.`,
        },
        {
            question: `Can I book ${listing.name} online?`,
            answer: `Yes. Use the "Check availability" button to see live availability and book directly through mySpace.`,
        },
        listing.amenities && {
            question: `What amenities does ${listing.name} offer?`,
            answer: `Amenities include ${listing.amenities.replace(/[,;]/g, ', ')}. Each listing page shows the full updated list.`,
        },
        {
            question: `Is ${listing.name} verified by mySpace?`,
            answer: `Yes. Every ${singular.toLowerCase()} on mySpace passes owner identity, address, and basic safety verification before going live.`,
        },
    ].filter((f): f is { question: string; answer: string } => Boolean(f));
}


export const ListingDetailPage: React.FC = () => {
    const { category, slug } = useParams<{ category: string; slug: string }>();
    const cat = category && isKnownCategory(category) ? category : null;

    const [listing, setListing] = useState<PublicListing | null>(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);

    useEffect(() => {
        let cancelled = false;
        async function run() {
            if (!cat || !slug) { setNotFound(true); setLoading(false); return; }
            setLoading(true);
            try {
                const res = await publicService.getListing(cat, slug);
                if (!cancelled) setListing(res.listing);
            } catch {
                if (!cancelled) setNotFound(true);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        void run();
        return () => { cancelled = true; };
    }, [cat, slug]);

    const images = useMemo(() => {
        return (listing?.images || '')
            .split(',')
            .map(s => s.trim())
            .filter(Boolean);
    }, [listing?.images]);

    const amenities = useMemo(() => {
        return (listing?.amenities || '')
            .split(/[,;]/)
            .map(s => s.trim())
            .filter(Boolean);
    }, [listing?.amenities]);

    const canonical = cat && slug
        ? `${SITE_ORIGIN}/listing/${cat}/${slug}`
        : SITE_ORIGIN;

    const schema = useMemo(() => {
        if (!listing || !cat) return [];
        const out: object[] = [];
        out.push(breadcrumbList([
            { name: 'mySpace', url: SITE_ORIGIN },
            { name: CATEGORY_LABELS[cat], url: `${SITE_ORIGIN}/${cat}` },
            ...(listing.city ? [{
                name: listing.city,
                url: `${SITE_ORIGIN}/${cat}/${listing.city.toLowerCase()}`,
            }] : []),
            { name: listing.name, url: canonical },
        ]));
        out.push(localBusiness({
            kind: SCHEMA_KIND[cat],
            name: listing.name,
            description: listing.description || `${CATEGORY_SINGULAR[cat]} in ${listing.city || 'India'}.`,
            url: canonical,
            image: images.length > 0 ? images : [`${SITE_ORIGIN}/logo_stacked.png`],
            streetAddress: listing.address || undefined,
            addressLocality: listing.city || 'India',
            addressRegion: listing.state || '',
            postalCode: listing.pincode || undefined,
            latitude: listing.lat ?? undefined,
            longitude: listing.lng ?? undefined,
            priceRange: listing.price_start
                ? `₹${listing.price_start.toLocaleString('en-IN')}+`
                : undefined,
            amenityFeature: amenities.length > 0 ? amenities : undefined,
            offers: listing.price_start != null ? [{
                price: listing.price_start,
                currency: 'INR',
                description: `${CATEGORY_SINGULAR[cat]} monthly rate`,
            }] : undefined,
        }));
        out.push(faqPage(generateFAQs({ listing, category: cat })));
        return out;
    }, [listing, cat, canonical, images, amenities]);

    if (loading) {
        return <div className="max-w-3xl mx-auto px-4 py-24 text-gray-500">Loading…</div>;
    }
    if (notFound || !listing || !cat) {
        return (
            <div className="max-w-3xl mx-auto px-4 py-24 text-center">
                <h1 className="text-3xl font-bold text-gray-900">Listing not found</h1>
                <p className="text-gray-500 mt-2">
                    This listing may have been removed. Browse{' '}
                    <Link to={cat ? `/${cat}` : '/'} className="text-indigo-700 underline">
                        all {cat ? CATEGORY_LABELS[cat] : 'listings'}
                    </Link>.
                </p>
            </div>
        );
    }

    const place = [listing.locality, listing.city].filter(Boolean).join(', ');
    const title = `${listing.name}${place ? ` in ${place}` : ''}`;
    const description = listing.description
        || `${CATEGORY_SINGULAR[cat]} in ${place || 'India'}. ${listing.price_start ? `From ₹${listing.price_start.toLocaleString('en-IN')}/month.` : ''}`.trim();
    const heroImage = images[0] || `${SITE_ORIGIN}/logo_stacked.png`;
    const faqs = generateFAQs({ listing, category: cat });

    return (
        <>
            <SEO
                title={title}
                description={description}
                canonical={canonical}
                image={heroImage}
                ogType="product"
                schema={schema}
            />

            <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
                <Link to={`/${cat}`} className="inline-flex items-center text-sm text-indigo-700 hover:underline">
                    <ChevronLeft className="w-4 h-4" /> Back to {CATEGORY_LABELS[cat]}
                </Link>
            </div>

            {/* Hero — picture/srcset for the single LCP image + smaller
                lazy-loaded thumbnails for the gallery. */}
            <section className="max-w-6xl mx-auto px-4 sm:px-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="aspect-[4/3] bg-gray-100 rounded-2xl overflow-hidden">
                        {images[0] ? (
                            <ResponsiveImage
                                source={images[0]}
                                widths={IMAGE_PRESETS.hero}
                                sizes="(min-width: 768px) 50vw, 100vw"
                                alt={listing.name}
                                priority
                                width={1200}
                                height={900}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                            />
                        ) : (
                            <div className="w-full h-full grid place-items-center text-gray-300 text-6xl font-bold">
                                {listing.name.charAt(0)}
                            </div>
                        )}
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        {images.slice(1, 5).map((img, i) => (
                            <div key={i} className="aspect-square bg-gray-100 rounded-xl overflow-hidden">
                                <ResponsiveImage
                                    source={img}
                                    widths={IMAGE_PRESETS.thumb}
                                    sizes="(min-width: 768px) 25vw, 50vw"
                                    alt={`${listing.name} photo ${i + 2}`}
                                    width={480}
                                    height={480}
                                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                />
                            </div>
                        ))}
                        {Array.from({ length: Math.max(0, 4 - Math.max(0, images.length - 1)) }).map((_, i) => (
                            <div key={`ph-${i}`} className="aspect-square bg-gray-100 rounded-xl" />
                        ))}
                    </div>
                </div>
            </section>

            {/* Title + price + CTA */}
            <section className="max-w-6xl mx-auto px-4 sm:px-6 py-8 grid md:grid-cols-3 gap-8">
                <div className="md:col-span-2">
                    <div className="flex items-center gap-2 text-xs text-green-700 mb-2">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Verified by mySpace
                    </div>
                    <h1 className="text-3xl font-bold tracking-tight text-gray-900">{listing.name}</h1>
                    {place && (
                        <p className="mt-2 text-gray-500 flex items-center gap-1">
                            <MapPin className="w-4 h-4" /> {place}
                        </p>
                    )}

                    {listing.description && (
                        <div className="mt-6">
                            <h2 className="text-lg font-semibold text-gray-900 mb-2">About this {CATEGORY_SINGULAR[cat].toLowerCase()}</h2>
                            <p className="text-gray-700 leading-relaxed whitespace-pre-line">{listing.description}</p>
                        </div>
                    )}

                    {amenities.length > 0 && (
                        <div className="mt-8">
                            <h2 className="text-lg font-semibold text-gray-900 mb-3">Amenities</h2>
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                {amenities.map(a => (
                                    <div key={a} className="flex items-center gap-2 text-sm text-gray-700">
                                        <CheckCircle2 className="w-4 h-4 text-indigo-600" /> {a}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {listing.address && (
                        <div className="mt-8">
                            <h2 className="text-lg font-semibold text-gray-900 mb-2">Location</h2>
                            <p className="text-gray-700">{listing.address}</p>
                            {listing.lat != null && listing.lng != null && (
                                <a
                                    href={`https://www.google.com/maps?q=${listing.lat},${listing.lng}`}
                                    target="_blank" rel="noopener noreferrer"
                                    className="inline-flex items-center text-sm text-indigo-700 mt-2 hover:underline"
                                >
                                    Open in Google Maps <ExternalLink className="w-3 h-3 ml-1" />
                                </a>
                            )}
                        </div>
                    )}
                </div>

                <aside className="md:col-span-1">
                    <div className="border border-gray-200 rounded-xl p-5 sticky top-24 bg-white">
                        {listing.price_start != null ? (
                            <div className="mb-4">
                                <div className="text-2xl font-bold text-gray-900">
                                    ₹{listing.price_start.toLocaleString('en-IN')}
                                    <span className="text-sm font-normal text-gray-500">/month</span>
                                </div>
                                <div className="text-xs text-gray-500 mt-1">Starting price</div>
                            </div>
                        ) : (
                            <div className="mb-4 text-sm text-gray-500">Contact owner for pricing</div>
                        )}
                        <Link
                            to={`/student/reading-room/${listing.id}`}
                            className="block w-full text-center bg-indigo-600 text-white font-semibold py-3 rounded-lg hover:bg-indigo-700"
                        >
                            Check availability
                        </Link>
                        <Link
                            to="/login"
                            className="block w-full text-center border border-indigo-200 text-indigo-700 font-medium py-2.5 rounded-lg mt-2 hover:bg-indigo-50"
                        >
                            Contact owner
                        </Link>
                    </div>
                </aside>
            </section>

            {/* FAQs */}
            <section className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">Frequently asked questions</h2>
                <div className="space-y-4">
                    {faqs.map(f => (
                        <details key={f.question} className="group border border-gray-200 rounded-lg p-4 bg-white">
                            <summary className="cursor-pointer font-medium text-gray-900 list-none flex justify-between items-center">
                                {f.question}
                                <span className="text-indigo-600 group-open:rotate-180 transition-transform">▾</span>
                            </summary>
                            <p className="mt-3 text-gray-600 text-sm leading-relaxed">{f.answer}</p>
                        </details>
                    ))}
                </div>
            </section>
        </>
    );
};

export default ListingDetailPage;
