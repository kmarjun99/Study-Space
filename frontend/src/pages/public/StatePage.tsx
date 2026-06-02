/**
 * State overview page — `/state/:slug`.
 *
 * Aggregates every city in the state and links into the per-city page.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { SEO } from '../../seo/SEO';
import { breadcrumbList, faqPage, place, SITE_ORIGIN } from '../../seo/schema';
import { LocationResponse, publicService } from '../../services/publicService';


export const StatePage: React.FC = () => {
    const { slug } = useParams<{ slug: string }>();
    const [res, setRes] = useState<LocationResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);

    useEffect(() => {
        let cancelled = false;
        async function run() {
            if (!slug) { setNotFound(true); setLoading(false); return; }
            try {
                const r = await publicService.getLocation('state', slug);
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

    const canonical = `${SITE_ORIGIN}/state/${slug}`;
    const stateName = res?.location.name ?? '';

    const description = stateName
        ? `Discover reading rooms, study cabins, PGs, hostels, co-working and rental spaces across ${stateName}. Verified listings in every major city.`
        : '';

    const faqs = useMemo(() => res ? [
        {
            question: `Which cities in ${stateName} are on mySpace?`,
            answer: res.children.length > 0
                ? `Live coverage includes ${res.children.slice(0, 8).map(c => c.name).join(', ')}, with more cities being added.`
                : `${stateName} cities are being onboarded onto mySpace.`,
        },
        {
            question: `What types of spaces can I find in ${stateName}?`,
            answer: `mySpace covers reading rooms, study cabins, PGs, hostels, co-working spaces, co-learning spaces, rental houses, and rooms for rent.`,
        },
        {
            question: `Are mySpace listings in ${stateName} verified?`,
            answer: `Yes — every listing passes owner identity, address, and basic safety checks before going live.`,
        },
    ] : [], [res, stateName]);

    const schema = useMemo(() => {
        if (!res) return [];
        const out: object[] = [];
        out.push(breadcrumbList([
            { name: 'mySpace', url: SITE_ORIGIN },
            { name: stateName, url: canonical },
        ]));
        if (faqs.length) out.push(faqPage(faqs));
        if (res.location.lat != null && res.location.lng != null) {
            out.push(place({
                name: stateName,
                description,
                url: canonical,
                latitude: res.location.lat,
                longitude: res.location.lng,
            }));
        }
        return out;
    }, [res, stateName, canonical, faqs, description]);

    if (loading) return <div className="max-w-3xl mx-auto px-4 py-24 text-gray-500">Loading…</div>;
    if (notFound || !res) {
        return (
            <div className="max-w-3xl mx-auto px-4 py-24 text-center">
                <h1 className="text-3xl font-bold text-gray-900">State not found</h1>
                <p className="text-gray-500 mt-2">
                    <Link to="/" className="text-indigo-700 underline">Browse our homepage</Link>.
                </p>
            </div>
        );
    }

    return (
        <>
            <SEO
                title={`${stateName} — Reading Rooms, PGs, Hostels & More Across Every City`}
                description={description}
                canonical={canonical}
                schema={schema}
            />

            <section className="bg-gradient-to-b from-indigo-50 to-white border-b border-gray-100">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 py-14">
                    <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-gray-900">
                        Spaces across {stateName}
                    </h1>
                    <p className="mt-4 max-w-3xl text-gray-700 text-lg leading-relaxed">{description}</p>
                </div>
            </section>

            {res.children.length > 0 && (
                <section className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
                    <h2 className="text-xl font-semibold text-gray-900 mb-6">
                        Cities in {stateName}
                    </h2>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                        {res.children.map(c => (
                            <Link
                                key={c.id}
                                to={`/city/${c.slug}`}
                                className="block bg-white border border-gray-200 rounded-xl p-5 hover:border-indigo-300 hover:shadow-sm"
                            >
                                <div className="font-semibold text-gray-900 flex items-center gap-1">
                                    <MapPin className="w-3.5 h-3.5 text-indigo-600" />
                                    {c.name}
                                </div>
                                {c.aliases.length > 0 && (
                                    <div className="text-xs text-gray-500 mt-1">{c.aliases[0]}</div>
                                )}
                            </Link>
                        ))}
                    </div>
                </section>
            )}

            <section className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">FAQs about {stateName}</h2>
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

export default StatePage;
