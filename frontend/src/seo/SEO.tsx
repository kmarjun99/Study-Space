/**
 * <SEO> — single point of truth for per-page head metadata.
 *
 * Use it inside any route component to declare:
 *   - <title>, <meta name="description">
 *   - <link rel="canonical">
 *   - Open Graph + Twitter cards
 *   - JSON-LD schema (LocalBusiness / FAQPage / Article / ItemList / etc.)
 *
 * The Organization + WebSite + SearchAction graph is always present in
 * index.html, so we never have to re-declare it.
 *
 * Example:
 *   <SEO
 *     title="Reading Rooms in Kochi — mySpace"
 *     description="47 verified reading rooms in Kochi from ₹1,500/month."
 *     canonical="https://myspaceapp.in/reading-rooms/kochi"
 *     image="https://myspaceapp.in/og/reading-rooms-kochi.png"
 *     schema={[itemListJsonLd, faqJsonLd]}
 *   />
 */
import React from 'react';
import { Helmet } from 'react-helmet-async';

const SITE_NAME = 'mySpace';
const SITE_ORIGIN = 'https://myspaceapp.in';
const DEFAULT_IMAGE = `${SITE_ORIGIN}/logo_stacked.png`;
const DEFAULT_DESCRIPTION =
    "mySpace is India's discovery and booking platform for reading rooms, " +
    "study cabins, PGs, hostels, co-working and co-learning spaces.";

export interface SEOProps {
    /** Full page title — we append "| mySpace" only if missing. */
    title: string;
    description?: string;
    /** Absolute canonical URL. Falls back to the current pathname. */
    canonical?: string;
    /** Absolute URL of the share image. Defaults to the stacked logo. */
    image?: string;
    /**
     * Robots directive override. Use 'noindex, follow' for thin/staged pages.
     * Default 'index, follow' is suitable for every SEO landing page.
     */
    robots?: string;
    /**
     * Open Graph type — 'website' (default), 'article', 'product', etc.
     * Listings should use 'product'; guides should use 'article'.
     */
    ogType?: string;
    /**
     * One or more JSON-LD objects (already typed by the caller). Each is
     * stringified and emitted as a separate <script type="application/ld+json">.
     * Pass arrays-of-objects to compose a @graph if desired.
     */
    schema?: object | object[];
    /**
     * Locale override. en-IN by default. Switch to ml-IN / ta-IN / hi-IN
     * when localized pages ship.
     */
    locale?: string;
}

function resolveCanonical(explicit?: string): string {
    if (explicit) return explicit;
    if (typeof window === 'undefined') return `${SITE_ORIGIN}/`;
    // Strip query + hash — canonical never includes session-y junk.
    return `${SITE_ORIGIN}${window.location.pathname}`;
}

function ensureBranded(title: string): string {
    if (title.toLowerCase().includes('myspace')) return title;
    return `${title} | ${SITE_NAME}`;
}

export const SEO: React.FC<SEOProps> = ({
    title,
    description = DEFAULT_DESCRIPTION,
    canonical,
    image = DEFAULT_IMAGE,
    robots = 'index, follow, max-image-preview:large, max-snippet:-1',
    ogType = 'website',
    schema,
    locale = 'en-IN',
}) => {
    const fullTitle = ensureBranded(title);
    const resolvedCanonical = resolveCanonical(canonical);
    const schemaArray = schema
        ? Array.isArray(schema) ? schema : [schema]
        : [];

    return (
        <Helmet prioritizeSeoTags>
            <title>{fullTitle}</title>
            <meta name="description" content={description} />
            <meta name="robots" content={robots} />
            <link rel="canonical" href={resolvedCanonical} />

            {/* Open Graph */}
            <meta property="og:type" content={ogType} />
            <meta property="og:site_name" content={SITE_NAME} />
            <meta property="og:title" content={fullTitle} />
            <meta property="og:description" content={description} />
            <meta property="og:url" content={resolvedCanonical} />
            <meta property="og:image" content={image} />
            <meta property="og:locale" content={locale.replace('-', '_')} />

            {/* Twitter */}
            <meta name="twitter:card" content="summary_large_image" />
            <meta name="twitter:title" content={fullTitle} />
            <meta name="twitter:description" content={description} />
            <meta name="twitter:image" content={image} />

            <html lang={locale} />

            {/* Per-page JSON-LD. The Organization + WebSite graph from
                index.html is always present — no need to repeat it. */}
            {schemaArray.map((obj, i) => (
                <script
                    key={i}
                    type="application/ld+json"
                >
                    {JSON.stringify(obj)}
                </script>
            ))}
        </Helmet>
    );
};

export default SEO;
