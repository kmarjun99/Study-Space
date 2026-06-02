/**
 * Universal category page — handles three URL shapes:
 *
 *   /reading-rooms                     → category landing
 *   /reading-rooms/kochi               → city × category
 *   /reading-rooms/kochi/kakkanad      → locality × category
 *
 * Same component for all 10 categories. Resolves the right SEO copy,
 * fetches the matching listings, emits ItemList + FAQPage + Breadcrumb
 * + Place schema, and renders a grid + FAQs + nearby-localities links.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin, ArrowRight, ChevronLeft } from 'lucide-react';
import { SEO } from '../../seo/SEO';
import ResponsiveImage from '../../components/ResponsiveImage';
import { IMAGE_PRESETS, firstImage } from '../../utils/imageUtils';
import {
    breadcrumbList, faqPage, itemList, place, SITE_ORIGIN,
} from '../../seo/schema';
import {
    Category, CATEGORY_LABELS, CATEGORY_SINGULAR,
    isKnownCategory, publicService,
    LocationResponse, ListingsResponse,
} from '../../services/publicService';


// ---------- intent-rich content templates --------------------------------
//
// We deliberately do NOT generate paragraphs with an LLM at runtime. That
// would risk thin/spammy content. Instead we compose from a small set of
// templated phrases with real numbers (`count`, `cityName`). The result is
// unique per page but always factually grounded.

function makeIntro(args: {
    category: Category;
    cityName?: string;
    localityName?: string;
    count: number;
}): string {
    const label = CATEGORY_LABELS[args.category].toLowerCase();
    const singular = CATEGORY_SINGULAR[args.category].toLowerCase();
    if (args.localityName && args.cityName) {
        return args.count > 0
            ? `Browse ${args.count} verified ${label} in ${args.localityName}, ${args.cityName}. Filter by price, amenities, and distance to nearby landmarks — book online or visit directly.`
            : `${args.localityName} is a sought-after area for students and working professionals in ${args.cityName}. We're onboarding ${label} here — list yours to be among the first.`;
    }
    if (args.cityName) {
        return args.count > 0
            ? `Find your ideal ${singular} in ${args.cityName}. ${args.count} verified listings across the city — compare prices, amenities, and availability before you book.`
            : `${args.cityName} ${label} are being onboarded onto mySpace. Be the first to list yours or browse our nationwide network.`;
    }
    return `Discover and book ${label} across India. Verified owners, transparent pricing, no hidden fees. Filter by city, locality, budget, and amenities.`;
}

function makeFAQs(args: {
    category: Category;
    cityName?: string;
    localityName?: string;
    count: number;
}) {
    const place = args.localityName
        ? `${args.localityName}, ${args.cityName}`
        : args.cityName ?? 'India';
    const label = CATEGORY_LABELS[args.category].toLowerCase();
    const singular = CATEGORY_SINGULAR[args.category].toLowerCase();
    return [
        {
            question: `How many ${label} are available in ${place} on mySpace?`,
            answer: args.count > 0
                ? `As of today, mySpace lists ${args.count} verified ${label} in ${place}. The list updates daily as new listings come online.`
                : `We're onboarding ${label} owners in ${place} right now. New listings appear within 48 hours of verification.`,
        },
        {
            question: `What is the price range for a ${singular} in ${place}?`,
            answer: `Prices vary by amenities, location and seat type. ${args.count > 0 ? 'Use the filters above to set your budget and see real-time pricing across all available listings.' : 'Once listings are live you can filter by price band.'}`,
        },
        {
            question: `Are mySpace ${label} verified?`,
            answer: `Yes. Every listing on mySpace passes a verification check covering owner identity, address, and basic safety standards before going live.`,
        },
        {
            question: `Can I book a ${singular} online?`,
            answer: `Yes — most ${label} on mySpace accept online bookings with instant confirmation. Some allow visits first; you'll see the option on each listing page.`,
        },
        {
            question: `Does mySpace offer ${label} for both students and working professionals?`,
            answer: `Yes. Listings tag their preferred audience (students, working professionals, or both) on the listing page itself.`,
        },
    ];
}


// ---------- presentation pieces -------------------------------------------

const ListingCard: React.FC<{
    listing: ListingsResponse['listings'][number];
    category: Category;
}> = ({ listing, category }) => {
    const detailHref = listing.slug
        ? `/listing/${category}/${listing.slug}`
        : `#`;
    const firstImg = firstImage(listing.images);
    return (
        <Link to={detailHref} className="group block bg-white border border-gray-200 rounded-xl overflow-hidden hover:shadow-md transition-shadow">
            <div className="aspect-[4/3] bg-gray-100 overflow-hidden">
                {firstImg ? (
                    <ResponsiveImage
                        source={firstImg}
                        widths={IMAGE_PRESETS.card}
                        sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
                        alt={listing.name}
                        width={640}
                        height={480}
                        className="group-hover:scale-105 transition-transform"
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                ) : (
                    <div className="w-full h-full grid place-items-center text-gray-300 text-4xl font-bold">
                        {listing.name.charAt(0)}
                    </div>
                )}
            </div>
            <div className="p-4">
                <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-gray-900 line-clamp-1">{listing.name}</h3>
                    {listing.is_sponsored && (
                        <span className="text-[10px] uppercase tracking-wide bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">
                            Promoted
                        </span>
                    )}
                </div>
                {(listing.locality || listing.city) && (
                    <p className="text-sm text-gray-500 mt-1 flex items-center gap-1">
                        <MapPin className="w-3 h-3" />
                        {[listing.locality, listing.city].filter(Boolean).join(', ')}
                    </p>
                )}
                {listing.price_start != null && (
                    <div className="mt-3 text-sm">
                        <span className="text-gray-500">From </span>
                        <span className="font-semibold text-gray-900">
                            ₹{listing.price_start.toLocaleString('en-IN')}
                        </span>
                        <span className="text-gray-500">/month</span>
                    </div>
                )}
            </div>
        </Link>
    );
};


const FAQsBlock: React.FC<{ faqs: { question: string; answer: string }[] }> = ({ faqs }) => (
    <section className="max-w-3xl mx-auto py-12">
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
);


// ---------- the page itself ----------------------------------------------

interface CategoryPageProps {
    /** Forced category from a literal route. Use this when the route is
     *  e.g. `/study-cabins` (no URL param) — the parent router passes the
     *  category in directly so we don't have to fish it out of useParams. */
    forcedCategory?: string;
}

export const CategoryPage: React.FC<CategoryPageProps> = ({ forcedCategory }) => {
    const { category, citySlug, localitySlug } = useParams<{
        category: string;
        citySlug?: string;
        localitySlug?: string;
    }>();

    const resolvedCategory = forcedCategory ?? category;
    const cat = resolvedCategory && isKnownCategory(resolvedCategory) ? resolvedCategory : null;

    const [cityRes, setCityRes] = useState<LocationResponse | null>(null);
    const [localityRes, setLocalityRes] = useState<LocationResponse | null>(null);
    const [listings, setListings] = useState<ListingsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);

    useEffect(() => {
        let cancelled = false;
        async function run() {
            if (!cat) {
                setNotFound(true);
                setLoading(false);
                return;
            }
            setLoading(true);
            try {
                const [city, locality, l] = await Promise.all([
                    citySlug
                        ? publicService.getLocation('city', citySlug).catch(() => null)
                        : Promise.resolve(null),
                    localitySlug
                        ? publicService.getLocation('locality', localitySlug).catch(() => null)
                        : Promise.resolve(null),
                    publicService.listListings(cat, {
                        citySlug, localitySlug, limit: 48,
                    }),
                ]);
                if (cancelled) return;
                if (citySlug && !city) { setNotFound(true); return; }
                if (localitySlug && !locality) { setNotFound(true); return; }
                setCityRes(city);
                setLocalityRes(locality);
                setListings(l);
            } catch {
                if (!cancelled) setNotFound(true);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        void run();
        return () => { cancelled = true; };
    }, [cat, citySlug, localitySlug]);

    const cityName = cityRes?.location.name;
    const localityName = localityRes?.location.name;

    const titleParts = useMemo(() => {
        if (!cat) return ['mySpace'];
        if (localityName && cityName) {
            return [`${CATEGORY_LABELS[cat]} in ${localityName}, ${cityName}`];
        }
        if (cityName) return [`${CATEGORY_LABELS[cat]} in ${cityName}`];
        return [`${CATEGORY_LABELS[cat]} Across India`];
    }, [cat, cityName, localityName]);

    const canonical = useMemo(() => {
        if (!cat) return SITE_ORIGIN;
        const parts = [cat, citySlug, localitySlug].filter(Boolean).join('/');
        return `${SITE_ORIGIN}/${parts}`;
    }, [cat, citySlug, localitySlug]);

    const intro = useMemo(() => cat
        ? makeIntro({ category: cat, cityName, localityName, count: listings?.count ?? 0 })
        : '', [cat, cityName, localityName, listings?.count]);

    const faqs = useMemo(() => cat
        ? makeFAQs({ category: cat, cityName, localityName, count: listings?.count ?? 0 })
        : [], [cat, cityName, localityName, listings?.count]);

    const schema = useMemo(() => {
        if (!cat) return [];
        const out: object[] = [];
        const crumbs = [
            { name: 'mySpace', url: SITE_ORIGIN },
            { name: CATEGORY_LABELS[cat], url: `${SITE_ORIGIN}/${cat}` },
        ];
        if (cityName && citySlug) {
            crumbs.push({ name: cityName, url: `${SITE_ORIGIN}/${cat}/${citySlug}` });
        }
        if (localityName && citySlug && localitySlug) {
            crumbs.push({
                name: localityName,
                url: `${SITE_ORIGIN}/${cat}/${citySlug}/${localitySlug}`,
            });
        }
        out.push(breadcrumbList(crumbs));
        if (faqs.length) out.push(faqPage(faqs));
        if (listings?.listings.length) {
            out.push(itemList(listings.listings.slice(0, 25).map(l => ({
                name: l.name,
                url: l.slug ? `${SITE_ORIGIN}/listing/${cat}/${l.slug}` : `${SITE_ORIGIN}/${cat}`,
            }))));
        }
        const placeRow = localityRes?.location || cityRes?.location;
        if (placeRow && placeRow.lat != null && placeRow.lng != null) {
            out.push(place({
                name: placeRow.name,
                description: intro,
                url: canonical,
                latitude: placeRow.lat,
                longitude: placeRow.lng,
                containedInPlace: cityRes?.location && localityRes
                    ? { name: cityRes.location.name }
                    : undefined,
            }));
        }
        return out;
    }, [cat, cityName, citySlug, localityName, localitySlug, listings, faqs, canonical, cityRes, localityRes, intro]);

    if (!cat || notFound) {
        return (
            <div className="max-w-3xl mx-auto px-4 py-24 text-center">
                <h1 className="text-3xl font-bold text-gray-900">Page not found</h1>
                <p className="text-gray-500 mt-2">
                    The page you're looking for doesn't exist (yet). Browse our{' '}
                    <Link to="/" className="text-indigo-700 underline">homepage</Link> instead.
                </p>
            </div>
        );
    }

    const heading = titleParts[0];
    const description = intro;

    return (
        <>
            <SEO
                title={heading}
                description={description}
                canonical={canonical}
                schema={schema}
            />

            <section className="bg-gradient-to-b from-indigo-50 to-white border-b border-gray-100">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
                    {cityRes && (
                        <Link
                            to={localitySlug ? `/${cat}/${citySlug}` : `/${cat}`}
                            className="inline-flex items-center text-sm text-indigo-700 hover:underline mb-4"
                        >
                            <ChevronLeft className="w-4 h-4" />
                            {localitySlug ? `Back to ${cityName}` : `Back to ${CATEGORY_LABELS[cat]}`}
                        </Link>
                    )}
                    <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-gray-900">
                        {heading}
                    </h1>
                    <p className="mt-4 max-w-3xl text-gray-700 text-lg leading-relaxed">{description}</p>

                    {/* Nearby localities — shown on city × category pages */}
                    {!localitySlug && cityRes && cityRes.children.length > 0 && (
                        <div className="mt-6 flex flex-wrap gap-2">
                            {cityRes.children.slice(0, 12).map(child => (
                                <Link
                                    key={child.id}
                                    to={`/${cat}/${citySlug}/${child.slug}`}
                                    className="text-xs bg-white border border-gray-200 rounded-full px-3 py-1.5 text-gray-700 hover:border-indigo-300 hover:text-indigo-700"
                                >
                                    {CATEGORY_LABELS[cat]} in {child.name}
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
            </section>

            <section className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
                {loading ? (
                    <div className="text-gray-500">Loading listings…</div>
                ) : listings && listings.count > 0 ? (
                    <>
                        <div className="flex items-baseline justify-between mb-6">
                            <h2 className="text-xl font-semibold text-gray-900">
                                {listings.count} {CATEGORY_LABELS[cat]}{cityName ? ` in ${cityName}` : ''}
                            </h2>
                            <Link to={`/${cat}`} className="text-sm text-indigo-700 hover:underline">
                                View all {CATEGORY_LABELS[cat]} <ArrowRight className="inline w-3 h-3" />
                            </Link>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                            {listings.listings.map(l => (
                                <ListingCard key={l.id} listing={l} category={cat} />
                            ))}
                        </div>
                    </>
                ) : (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-8 text-center">
                        <h2 className="text-lg font-semibold text-amber-900 mb-2">
                            No {CATEGORY_LABELS[cat]} listed yet{cityName ? ` in ${cityName}` : ''}
                        </h2>
                        <p className="text-amber-800 text-sm max-w-md mx-auto">
                            We're actively onboarding owners. If you own a {CATEGORY_SINGULAR[cat]}, list it on mySpace
                            and be among the first to appear here.
                        </p>
                        <Link
                            to="/register"
                            className="inline-block mt-4 bg-amber-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-amber-700"
                        >
                            List your {CATEGORY_SINGULAR[cat]}
                        </Link>
                    </div>
                )}
            </section>

            <FAQsBlock faqs={faqs} />
        </>
    );
};

export default CategoryPage;
