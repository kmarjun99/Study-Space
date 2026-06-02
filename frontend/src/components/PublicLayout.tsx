/**
 * Public-facing site shell. Lightweight header + footer used for every
 * SEO-indexed route (`/`, `/reading-rooms/...`, `/listing/...`, `/city/...`,
 * `/state/...`, `/guides/...`, `/about`, etc.).
 *
 * Deliberately separate from the in-app Layout (which has the role-based
 * sidebar). Logged-in users hitting public URLs see this same shell so the
 * SEO experience is consistent.
 */
import React from 'react';
import { Link, Outlet } from 'react-router-dom';
import { Menu, X, Search, MapPin } from 'lucide-react';
import { CATEGORIES, CATEGORY_LABELS, Category } from '../services/publicService';

const FEATURED_CITIES = [
    { slug: 'kochi', name: 'Kochi' },
    { slug: 'trivandrum', name: 'Trivandrum' },
    { slug: 'bangalore', name: 'Bangalore' },
    { slug: 'chennai', name: 'Chennai' },
    { slug: 'hyderabad', name: 'Hyderabad' },
    { slug: 'mumbai', name: 'Mumbai' },
    { slug: 'pune', name: 'Pune' },
    { slug: 'delhi', name: 'New Delhi' },
];

const HEADER_CATEGORIES: Category[] = [
    'reading-rooms', 'study-cabins', 'pgs', 'hostels', 'co-working-spaces',
];

export const PublicLayout: React.FC = () => {
    const [open, setOpen] = React.useState(false);

    return (
        <div className="min-h-screen flex flex-col bg-white text-gray-900 antialiased">
            <header className="border-b border-gray-200 bg-white sticky top-0 z-30">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between h-16">
                    <Link to="/" className="flex items-center gap-2 font-bold text-xl text-indigo-700">
                        <span className="inline-block w-7 h-7 rounded bg-indigo-600 text-white grid place-items-center text-sm">M</span>
                        mySpace
                    </Link>

                    <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-gray-700">
                        {HEADER_CATEGORIES.map(cat => (
                            <Link key={cat} to={`/${cat}`} className="hover:text-indigo-700 transition-colors">
                                {CATEGORY_LABELS[cat]}
                            </Link>
                        ))}
                        <Link to="/guides" className="hover:text-indigo-700">Guides</Link>
                    </nav>

                    <div className="flex items-center gap-3">
                        <Link
                            to="/login"
                            className="hidden sm:inline-flex text-sm font-medium text-gray-700 hover:text-indigo-700"
                        >
                            Sign in
                        </Link>
                        <Link
                            to="/register"
                            className="hidden sm:inline-flex bg-indigo-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-indigo-700"
                        >
                            List your space
                        </Link>
                        <button
                            className="md:hidden p-2 rounded hover:bg-gray-100"
                            onClick={() => setOpen(s => !s)}
                            aria-label="Toggle menu"
                        >
                            {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                        </button>
                    </div>
                </div>

                {open && (
                    <div className="md:hidden border-t border-gray-200 bg-white">
                        <div className="px-4 py-3 grid gap-2">
                            {CATEGORIES.map(cat => (
                                <Link key={cat} to={`/${cat}`} className="py-1.5 text-sm" onClick={() => setOpen(false)}>
                                    {CATEGORY_LABELS[cat]}
                                </Link>
                            ))}
                            <Link to="/guides" className="py-1.5 text-sm" onClick={() => setOpen(false)}>Guides</Link>
                            <Link to="/login" className="py-1.5 text-sm" onClick={() => setOpen(false)}>Sign in</Link>
                            <Link to="/register" className="py-1.5 text-sm text-indigo-700 font-medium" onClick={() => setOpen(false)}>
                                List your space
                            </Link>
                        </div>
                    </div>
                )}
            </header>

            <main className="flex-1">
                <Outlet />
            </main>

            <footer className="border-t border-gray-200 bg-gray-50 mt-16">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 py-12 grid grid-cols-2 md:grid-cols-5 gap-8 text-sm">
                    <div className="col-span-2">
                        <Link to="/" className="flex items-center gap-2 font-bold text-lg text-indigo-700">
                            <span className="inline-block w-6 h-6 rounded bg-indigo-600 text-white grid place-items-center text-xs">M</span>
                            mySpace
                        </Link>
                        <p className="mt-3 text-gray-600 max-w-xs">
                            India's discovery and booking platform for reading rooms, study cabins, PGs, hostels,
                            co-working and co-learning spaces.
                        </p>
                    </div>

                    <div>
                        <h4 className="font-semibold text-gray-900 mb-3">Categories</h4>
                        <ul className="space-y-2 text-gray-600">
                            {CATEGORIES.slice(0, 6).map(cat => (
                                <li key={cat}>
                                    <Link to={`/${cat}`} className="hover:text-indigo-700">
                                        {CATEGORY_LABELS[cat]}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div>
                        <h4 className="font-semibold text-gray-900 mb-3">Cities</h4>
                        <ul className="space-y-2 text-gray-600">
                            {FEATURED_CITIES.map(c => (
                                <li key={c.slug}>
                                    <Link to={`/city/${c.slug}`} className="hover:text-indigo-700">
                                        <MapPin className="w-3 h-3 inline mr-1" />
                                        {c.name}
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div>
                        <h4 className="font-semibold text-gray-900 mb-3">Company</h4>
                        <ul className="space-y-2 text-gray-600">
                            <li><Link to="/about" className="hover:text-indigo-700">About</Link></li>
                            <li><Link to="/press" className="hover:text-indigo-700">Press</Link></li>
                            <li><Link to="/careers" className="hover:text-indigo-700">Careers</Link></li>
                            <li><Link to="/contact" className="hover:text-indigo-700">Contact</Link></li>
                            <li><Link to="/trust" className="hover:text-indigo-700">Trust &amp; Safety</Link></li>
                            <li><Link to="/help" className="hover:text-indigo-700">Help</Link></li>
                        </ul>
                    </div>
                </div>

                <div className="border-t border-gray-200">
                    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 flex flex-col sm:flex-row justify-between gap-3 text-xs text-gray-500">
                        <div>© {new Date().getFullYear()} mySpace. All rights reserved.</div>
                        <div className="flex gap-4">
                            <Link to="/privacy" className="hover:text-indigo-700">Privacy</Link>
                            <Link to="/terms" className="hover:text-indigo-700">Terms</Link>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    );
};

// Re-export for convenience.
export const SearchIcon = Search;

export default PublicLayout;
