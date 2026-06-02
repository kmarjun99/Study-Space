/**
 * City overview page — /city/:slug
 *
 * One landing per city that aggregates inventory across all 10 categories.
 * Internal links: each category card → /{category}/{city} page;
 * locality chips → /{first-category}/{city}/{locality}.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin, BookOpen } from 'lucide-react';
import { SEO } from '../../seo/SEO';
import {
    breadcrumbList, faqPage, place, SITE_ORIGIN,
} from '../../seo/schema';
import {
    CATEGORIES, CATEGORY_LABELS, LocationResponse, publicService,
} from '../../services/publicService';


export const CityPage: React.FC = () => {
    const { slug } = useParams<{ slug: string }>();
    const [res, setRes] = useState<LocationResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);

    useEffect(() => {
        let cancelled = false;
        async function run() {
            if (!slug) { setNotFound(true); setLoading(false); return; }
            try {
                const r = await publicService.getLocation('city', slug);
                if (!cancelled) setRes(r);
            } catch {
                if (!cancelled) setNotFound(true);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        void run();
        return () => { cancelled = true; };
    }, [slug]);

    const canonical = `${SITE_ORIGIN}/city/${slug}`;
    const cityName = res?.location.name ?? '';
    const stateName = res?.breadcrumbs.find(b => b.kind === 'state')?.name;

    const description = cityName
        ? `Discover reading rooms, study cabins, PGs, hostels, co-working and rental spaces in ${cityName}${stateName ? `, ${stateName}` : ''}. Verified listings, transparent pricing, easy online booking.`
        : '';

    const faqs = useMemo(() => res ? [
        {
            question: `What spaces does mySpace offer in ${cityName}?`,
            answer: `mySpace lists reading rooms, study cabins, PGs, hostels, co-working spaces, co-learning spaces, rental houses and rooms for rent across ${cityName}.`,
        },
        {
            question: `Which areas of ${cityName} are covered?`,
            answer: res.children.length > 0
                ? `Popular localities include ${res.children.slice(0, 8).map(c => c.name).join(', ')}, and more.`
                : `We're actively expanding our locality coverage in ${cityName}.`,
        },
        {
            question: `Are all ${cityName} listings verified?`,
            answer: `Yes. Every listing passes owner identity, address, and basic safety checks before going live.`,
        },
        {
            question: `Can I book online for ${cityName}?`,
            answer: `Yes — most listings support online booking with instant confirmation.`,
        },
    ] : [], [res, cityName]);

    const schema = useMemo(() => {
        if (!res) return [];
        const out: object[] = [];
        out.push(breadcrumbList([
            { name: 'mySpace', url: SITE_ORIGIN },
            ...(stateName ? [{
                name: stateName,
                url: `${SITE_ORIGIN}/state/${res.breadcrumbs.find(b => b.kind === 'state')!.slug}`,
            }] : []),
            { name: cityName, url: canonical },
        ]));
        if (faqs.length) out.push(faqPage(faqs));
        if (res.location.lat != null && res.location.lng != null) {
            out.push(place({
                name: cityName,
                description,
                url: canonical,
                latitude: res.location.lat,
                longitude: res.location.lng,
            }));
        }
        return out;
    }, [res, cityName, stateName, canonical, faqs, description]);

    if (loading) return <div className="max-w-3xl mx-auto px-4 py-24 text-gray-500">Loading…</div>;
    if (notFound || !res) {
        return (
            <div className="max-w-3xl mx-auto px-4 py-24 text-center">
                <h1 className="text-3xl font-bold text-gray-900">City not found</h1>
                <p className="text-gray-500 mt-2">
                    <Link to="/" className="text-indigo-700 underline">Browse our homepage</Link>.
                </p>
            </div>
        );
    }

    return (
        <>
            <SEO
                title={`${cityName} — Reading Rooms, Study Cabins, PGs, Hostels & More`}
                description={description}
                canonical={canonical}
                schema={schema}
            />

            <section className="bg-gradient-to-b from-indigo-50 to-white border-b border-gray-100">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 py-14">
                    <p className="text-sm text-indigo-700 font-medium uppercase tracking-wide flex items-center gap-1">
                        <MapPin className="w-3.5 h-3.5" /> {stateName ? `${stateName}, ` : ''}India
                    </p>
                    <h1 className="mt-2 text-4xl sm:text-5xl font-bold tracking-tight text-gray-900">
                        Find your space in {cityName}
                    </h1>
                    <p className="mt-4 max-w-3xl text-gray-700 text-lg leading-relaxed">{description}</p>
                </div>
            </section>

            <section className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
                <h2 className="text-xl font-semibold text-gray-900 mb-6">Browse by category in {cityName}</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                    {CATEGORIES.map(cat => (
                        <Link
                            key={cat}
                            to={`/${cat}/${slug}`}
                            className="group block bg-white border border-gray-200 rounded-xl p-5 hover:border-indigo-300 hover:shadow-sm transition"
                        >
                            <BookOpen className="w-5 h-5 text-indigo-600 mb-3" />
                            <h3 className="font-semibold text-gray-900 text-sm">{CATEGORY_LABELS[cat]}</h3>
                            <p className="mt-1 text-xs text-gray-500">in {cityName}</p>
                        </Link>
                    ))}
                </div>
            </section>

            {res.children.length > 0 && (
                <section className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
                    <h2 className="text-xl font-semibold text-gray-900 mb-4">Popular areas in {cityName}</h2>
                    <div className="flex flex-wrap gap-2">
                        {res.children.map(child => (
                            <Link
                                key={child.id}
                                to={`/reading-rooms/${slug}/${child.slug}`}
                                className="text-sm bg-white border border-gray-200 rounded-full px-4 py-2 text-gray-700 hover:border-indigo-300 hover:text-indigo-700"
                            >
                                <MapPin className="inline w-3 h-3 mr-1" />
                                {child.name}
                            </Link>
                        ))}
                    </div>
                </section>
            )}

            <section className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">FAQs about spaces in {cityName}</h2>
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

export default CityPage;
