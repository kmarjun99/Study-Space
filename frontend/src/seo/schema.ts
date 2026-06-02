/**
 * JSON-LD builders for every schema type we'll emit across the site.
 *
 * Each helper returns a plain object that satisfies schema.org's recommended
 * shape for the corresponding entity. Pass them straight to <SEO schema=...>.
 *
 * Tested against Google's Rich Results Test in CI before each release.
 */

export const SITE_ORIGIN = 'https://myspaceapp.in';
export const ORG_ID = `${SITE_ORIGIN}/#organization`;
export const SITE_ID = `${SITE_ORIGIN}/#website`;

// ---------- BreadcrumbList ------------------------------------------------

export interface Crumb { name: string; url: string; }

export function breadcrumbList(crumbs: Crumb[]): object {
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: crumbs.map((c, i) => ({
            '@type': 'ListItem',
            position: i + 1,
            name: c.name,
            item: c.url,
        })),
    };
}

// ---------- FAQPage -------------------------------------------------------

export interface FAQ { question: string; answer: string; }

export function faqPage(faqs: FAQ[]): object {
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: faqs.map(f => ({
            '@type': 'Question',
            name: f.question,
            acceptedAnswer: {
                '@type': 'Answer',
                text: f.answer,
            },
        })),
    };
}

// ---------- ItemList (used on category × city pages) ---------------------

export interface ItemListEntry { name: string; url: string; image?: string; }

export function itemList(items: ItemListEntry[]): object {
    return {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        itemListElement: items.map((it, i) => ({
            '@type': 'ListItem',
            position: i + 1,
            url: it.url,
            name: it.name,
            ...(it.image ? { image: it.image } : {}),
        })),
    };
}

// ---------- LocalBusiness / LodgingBusiness (listing detail) -------------

export type LocalBusinessKind =
    | 'LocalBusiness' | 'LodgingBusiness' | 'Hostel'
    | 'Apartment' | 'Residence';

export interface BusinessSchemaInput {
    kind: LocalBusinessKind;
    name: string;
    description: string;
    url: string;
    image: string | string[];
    telephone?: string;
    streetAddress?: string;
    addressLocality: string;
    addressRegion: string;
    postalCode?: string;
    countryCode?: string;       // 'IN' default
    latitude?: number;
    longitude?: number;
    priceRange?: string;        // '₹₹' or '₹1,500 - ₹5,000'
    aggregateRating?: { ratingValue: number; reviewCount: number };
    offers?: Array<{ price: number; currency?: string; description?: string }>;
    amenityFeature?: string[];
}

export function localBusiness(b: BusinessSchemaInput): object {
    const out: any = {
        '@context': 'https://schema.org',
        '@type': b.kind,
        name: b.name,
        description: b.description,
        url: b.url,
        image: b.image,
        address: {
            '@type': 'PostalAddress',
            streetAddress: b.streetAddress,
            addressLocality: b.addressLocality,
            addressRegion: b.addressRegion,
            postalCode: b.postalCode,
            addressCountry: b.countryCode ?? 'IN',
        },
        ...(b.telephone ? { telephone: b.telephone } : {}),
        ...(b.latitude !== undefined && b.longitude !== undefined ? {
            geo: {
                '@type': 'GeoCoordinates',
                latitude: b.latitude,
                longitude: b.longitude,
            },
        } : {}),
        ...(b.priceRange ? { priceRange: b.priceRange } : {}),
        ...(b.aggregateRating ? {
            aggregateRating: {
                '@type': 'AggregateRating',
                ratingValue: b.aggregateRating.ratingValue,
                reviewCount: b.aggregateRating.reviewCount,
            },
        } : {}),
        ...(b.amenityFeature ? {
            amenityFeature: b.amenityFeature.map(name => ({
                '@type': 'LocationFeatureSpecification',
                name,
            })),
        } : {}),
    };
    if (b.offers && b.offers.length > 0) {
        out.makesOffer = b.offers.map(o => ({
            '@type': 'Offer',
            price: o.price,
            priceCurrency: o.currency ?? 'INR',
            description: o.description,
        }));
    }
    return out;
}

// ---------- Article / BlogPosting (guides) -------------------------------

export interface ArticleSchemaInput {
    headline: string;
    description: string;
    url: string;
    image: string;
    datePublished: string;     // ISO date
    dateModified?: string;
    authorName?: string;
}

export function article(a: ArticleSchemaInput): object {
    return {
        '@context': 'https://schema.org',
        '@type': 'Article',
        headline: a.headline,
        description: a.description,
        image: a.image,
        datePublished: a.datePublished,
        dateModified: a.dateModified ?? a.datePublished,
        author: {
            '@type': 'Organization',
            name: a.authorName ?? 'mySpace',
            '@id': ORG_ID,
        },
        publisher: { '@id': ORG_ID },
        mainEntityOfPage: { '@type': 'WebPage', '@id': a.url },
    };
}

// ---------- Place (city / locality landing pages) -------------------------

export interface PlaceSchemaInput {
    name: string;
    description: string;
    url: string;
    latitude: number;
    longitude: number;
    containedInPlace?: { name: string; type?: 'City' | 'AdministrativeArea' };
}

export function place(p: PlaceSchemaInput): object {
    return {
        '@context': 'https://schema.org',
        '@type': 'Place',
        name: p.name,
        description: p.description,
        url: p.url,
        geo: {
            '@type': 'GeoCoordinates',
            latitude: p.latitude,
            longitude: p.longitude,
        },
        ...(p.containedInPlace ? {
            containedInPlace: {
                '@type': p.containedInPlace.type ?? 'City',
                name: p.containedInPlace.name,
            },
        } : {}),
    };
}
