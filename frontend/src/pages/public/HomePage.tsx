/**
 * Public home page — `/`.
 *
 * The single most-indexed page on the site. Designed to:
 *   - Answer "what is mySpace?" in the first 200 words (GEO/AEO)
 *   - List the 10 categories as anchor links (internal link equity)
 *   - Show featured cities (more anchor links)
 *   - Surface an FAQ block (FAQPage schema)
 *   - Direct conversions: list-your-space + sign-in
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BookOpen, Building2, Home, Briefcase, Users, ShieldCheck, Sparkles } from 'lucide-react';
import { SEO } from '../../seo/SEO';
import { faqPage, SITE_ORIGIN } from '../../seo/schema';
import { CATEGORIES, CATEGORY_LABELS } from '../../services/publicService';


const FEATURED_CITIES = [
    { slug: 'kochi', name: 'Kochi', state: 'Kerala' },
    { slug: 'trivandrum', name: 'Trivandrum', state: 'Kerala' },
    { slug: 'bangalore', name: 'Bangalore', state: 'Karnataka' },
    { slug: 'chennai', name: 'Chennai', state: 'Tamil Nadu' },
    { slug: 'hyderabad', name: 'Hyderabad', state: 'Telangana' },
    { slug: 'mumbai', name: 'Mumbai', state: 'Maharashtra' },
    { slug: 'pune', name: 'Pune', state: 'Maharashtra' },
    { slug: 'new-delhi', name: 'New Delhi', state: 'Delhi' },
    { slug: 'kolkata', name: 'Kolkata', state: 'West Bengal' },
    { slug: 'jaipur', name: 'Jaipur', state: 'Rajasthan' },
    { slug: 'patna', name: 'Patna', state: 'Bihar' },
    { slug: 'lucknow', name: 'Lucknow', state: 'Uttar Pradesh' },
];

const CATEGORY_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
    'reading-rooms': BookOpen,
    'study-cabins': BookOpen,
    'private-cabins': BookOpen,
    'shared-cabins': Users,
    'pgs': Home,
    'hostels': Building2,
    'co-working-spaces': Briefcase,
    'co-learning-spaces': Users,
    'rental-houses': Home,
    'rooms-for-rent': Home,
};

const FAQS = [
    {
        question: 'What is mySpace?',
        answer: 'mySpace is India\'s discovery and booking platform for reading rooms, study cabins, PGs, hostels, co-working spaces, co-learning spaces, rental houses and rooms for rent. We help students and working professionals find verified spaces and book them online.',
    },
    {
        question: 'Which cities does mySpace cover?',
        answer: 'mySpace is launching across India — starting with Kerala (all 14 districts) and expanding into Karnataka, Tamil Nadu, Telangana, Maharashtra, Delhi NCR, and beyond. Browse the City pages to see live coverage.',
    },
    {
        question: 'Are mySpace listings verified?',
        answer: 'Yes. Every owner passes identity, address, and basic safety checks before a listing goes live. Listings also display response time, ratings, and review history.',
    },
    {
        question: 'How do I book a reading room or PG on mySpace?',
        answer: 'Pick a listing, check availability, and pay through Razorpay. Confirmation is instant for most properties. You can also contact the owner directly to ask questions before booking.',
    },
    {
        question: 'How do owners list a property on mySpace?',
        answer: 'Owners sign up, complete a short verification, and publish their listing. There is no fixed listing fee — owners pick a plan that fits their property.',
    },
];

export const HomePage: React.FC = () => {
    return (
        <>
            <SEO
                title="mySpace — Reading Rooms, Study Cabins, PGs & Hostels Across India"
                description="mySpace is India's discovery and booking platform for reading rooms, study cabins, PGs, hostels, co-working and co-learning spaces. Verified listings across Kerala, Karnataka, Tamil Nadu and beyond."
                canonical={SITE_ORIGIN + '/'}
                schema={faqPage(FAQS)}
            />

            {/* Hero */}
            <section className="bg-gradient-to-b from-indigo-50 via-white to-white">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 py-16 sm:py-24 text-center">
                    <p className="text-sm font-medium text-indigo-700 uppercase tracking-wider mb-4 inline-flex items-center gap-1">
                        <Sparkles className="w-3.5 h-3.5" />
                        Verified spaces across India
                    </p>
                    <h1 className="text-4xl sm:text-6xl font-bold tracking-tight text-gray-900">
                        Reading rooms, PGs, hostels &amp; more.
                        <span className="block text-indigo-700">All in one place.</span>
                    </h1>
                    <p className="mt-6 max-w-2xl mx-auto text-lg text-gray-700 leading-relaxed">
                        mySpace helps students and working professionals discover and book verified
                        reading rooms, study cabins, PGs, hostels, co-working and co-learning spaces
                        across India.
                    </p>
                    <div className="mt-8 flex flex-col sm:flex-row justify-center gap-3">
                        <Link
                            to="/reading-rooms"
                            className="inline-flex items-center justify-center bg-indigo-600 text-white font-semibold px-6 py-3 rounded-lg hover:bg-indigo-700"
                        >
                            Browse reading rooms <ArrowRight className="ml-2 w-4 h-4" />
                        </Link>
                        <Link
                            to="/pgs"
                            className="inline-flex items-center justify-center border border-gray-300 bg-white text-gray-900 font-semibold px-6 py-3 rounded-lg hover:bg-gray-50"
                        >
                            Browse PGs &amp; hostels
                        </Link>
                    </div>
                </div>
            </section>

            {/* Categories grid */}
            <section className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">Find the right space</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                    {CATEGORIES.map(cat => {
                        const Icon = CATEGORY_ICONS[cat] ?? BookOpen;
                        return (
                            <Link
                                key={cat}
                                to={`/${cat}`}
                                className="group block bg-white border border-gray-200 rounded-xl p-5 hover:border-indigo-300 hover:shadow-sm transition"
                            >
                                <Icon className="w-6 h-6 text-indigo-600 mb-3" />
                                <h3 className="font-semibold text-gray-900 text-sm">{CATEGORY_LABELS[cat]}</h3>
                                <p className="mt-1 text-xs text-gray-500">Browse all →</p>
                            </Link>
                        );
                    })}
                </div>
            </section>

            {/* Featured cities */}
            <section className="bg-gray-50 border-y border-gray-200">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12">
                    <h2 className="text-2xl font-bold text-gray-900 mb-6">Explore by city</h2>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                        {FEATURED_CITIES.map(c => (
                            <Link
                                key={c.slug}
                                to={`/city/${c.slug}`}
                                className="block bg-white border border-gray-200 rounded-xl p-4 hover:border-indigo-300"
                            >
                                <div className="font-semibold text-gray-900">{c.name}</div>
                                <div className="text-xs text-gray-500 mt-1">{c.state}</div>
                            </Link>
                        ))}
                    </div>
                </div>
            </section>

            {/* Trust / why mySpace */}
            <section className="max-w-7xl mx-auto px-4 sm:px-6 py-16">
                <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">Why mySpace</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="bg-white border border-gray-200 rounded-xl p-6">
                        <ShieldCheck className="w-8 h-8 text-indigo-600 mb-3" />
                        <h3 className="font-semibold text-gray-900">Verified owners</h3>
                        <p className="mt-2 text-sm text-gray-600">
                            Every property passes identity, address and safety checks before listing.
                        </p>
                    </div>
                    <div className="bg-white border border-gray-200 rounded-xl p-6">
                        <Sparkles className="w-8 h-8 text-indigo-600 mb-3" />
                        <h3 className="font-semibold text-gray-900">Transparent pricing</h3>
                        <p className="mt-2 text-sm text-gray-600">
                            All-inclusive prices with full GST breakdown. No hidden fees, ever.
                        </p>
                    </div>
                    <div className="bg-white border border-gray-200 rounded-xl p-6">
                        <Briefcase className="w-8 h-8 text-indigo-600 mb-3" />
                        <h3 className="font-semibold text-gray-900">Instant booking</h3>
                        <p className="mt-2 text-sm text-gray-600">
                            Online payment, instant confirmation, secure escrow. Built for the way you work.
                        </p>
                    </div>
                </div>
            </section>

            {/* FAQs */}
            <section className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">Frequently asked questions</h2>
                <div className="space-y-4">
                    {FAQS.map(f => (
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

export default HomePage;
