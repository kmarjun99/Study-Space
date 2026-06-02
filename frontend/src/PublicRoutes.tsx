/**
 * Public route table — every URL that's indexable / shareable without auth.
 *
 * Mounted at the top of App.tsx BEFORE the auth-gated in-app shell so
 * Googlebot and unauthenticated visitors can reach these without bouncing
 * to login. Logged-in users see the same pages (no redirect to dashboard
 * on `/`).
 *
 * Path coverage:
 *   /                                     → HomePage
 *   /{category}                           → category landing
 *   /{category}/{city}                    → city × category
 *   /{category}/{city}/{locality}         → locality × category
 *   /listing/{category}/{slug}            → listing detail
 *   /city/{slug}                          → city overview
 *   /state/{slug}                         → state overview
 *   /about, /press, /careers, /contact,
 *   /trust, /help, /privacy, /terms       → entity pages
 */
import React, { lazy } from 'react';
import { Route } from 'react-router-dom';
import { CATEGORIES } from './services/publicService';

// PublicLayout is the shell — keep it eager so the header/footer render
// without a blink while a content chunk loads.
import PublicLayout from './components/PublicLayout';

// Every public page is lazy-loaded. In production these URLs are served
// as server-rendered Jinja2 HTML for SEO; the React versions are only
// reached when a logged-in or hash-routed user navigates client-side,
// so paying the small Suspense cost is fine.
const HomePage          = lazy(() => import('./pages/public/HomePage'));
const CategoryPage      = lazy(() => import('./pages/public/CategoryPage'));
const ListingDetailPage = lazy(() => import('./pages/public/ListingDetailPage'));
const CityPage          = lazy(() => import('./pages/public/CityPage'));
const StatePage         = lazy(() => import('./pages/public/StatePage'));

const EntityModule = () => import('./pages/public/EntityPages');
const AboutPage   = lazy(async () => ({ default: (await EntityModule()).AboutPage   }));
const PressPage   = lazy(async () => ({ default: (await EntityModule()).PressPage   }));
const CareersPage = lazy(async () => ({ default: (await EntityModule()).CareersPage }));
const ContactPage = lazy(async () => ({ default: (await EntityModule()).ContactPage }));
const TrustPage   = lazy(async () => ({ default: (await EntityModule()).TrustPage   }));
const HelpPage    = lazy(async () => ({ default: (await EntityModule()).HelpPage    }));
const PrivacyPage = lazy(async () => ({ default: (await EntityModule()).PrivacyPage }));
const TermsPage   = lazy(async () => ({ default: (await EntityModule()).TermsPage   }));


/**
 * Returns the JSX for all public routes. Used as children of a parent
 * <Route element={<PublicLayout />}> inside App.tsx.
 *
 * Why an array of <Route>s in a function instead of a component: React
 * Router needs <Route> elements to be direct children of <Routes>, so
 * we can't wrap them in a custom component.
 */
export function publicRoutes(): React.ReactNode {
    return (
        <>
            <Route element={<PublicLayout />}>
                <Route path="/" element={<HomePage />} />

                {/* Categories — three URL depths share one CategoryPage
                    component. Literal paths per category (NOT `/:category`)
                    so we don't accidentally swallow `/login`, `/register`,
                    `/auth`, or any other single-segment SPA route. The
                    category is passed as a `forcedCategory` prop, since
                    useParams() can't read it from a literal route. */}
                {CATEGORIES.map(cat => (
                    <React.Fragment key={cat}>
                        <Route path={`/${cat}`} element={<CategoryPage forcedCategory={cat} />} />
                        <Route path={`/${cat}/:citySlug`} element={<CategoryPage forcedCategory={cat} />} />
                        <Route path={`/${cat}/:citySlug/:localitySlug`} element={<CategoryPage forcedCategory={cat} />} />
                    </React.Fragment>
                ))}

                {/* Listing detail */}
                <Route path="/listing/:category/:slug" element={<ListingDetailPage />} />

                {/* Geo overviews */}
                <Route path="/city/:slug" element={<CityPage />} />
                <Route path="/state/:slug" element={<StatePage />} />

                {/* Entity pages */}
                <Route path="/about" element={<AboutPage />} />
                <Route path="/press" element={<PressPage />} />
                <Route path="/careers" element={<CareersPage />} />
                <Route path="/contact" element={<ContactPage />} />
                <Route path="/trust" element={<TrustPage />} />
                <Route path="/help" element={<HelpPage />} />
                <Route path="/privacy" element={<PrivacyPage />} />
                <Route path="/terms" element={<TermsPage />} />
            </Route>
        </>
    );
}

/**
 * Static set of public path prefixes — used by App.tsx to decide whether a
 * given URL should bypass the auth gate.
 */
export const PUBLIC_PATH_PREFIXES: string[] = [
    '/about', '/press', '/careers', '/contact',
    '/trust', '/help', '/privacy', '/terms',
    '/city/', '/state/', '/listing/',
    ...CATEGORIES.map(c => `/${c}`),
];

/**
 * Returns true when the path should be served by the public surface
 * (no auth required). Used at the top of App.tsx's render to decide
 * which shell to mount.
 */
export function isPublicPath(pathname: string): boolean {
    if (pathname === '/') return true;
    return PUBLIC_PATH_PREFIXES.some(p =>
        pathname === p || pathname.startsWith(p + '/') || pathname.startsWith(p)
    );
}
