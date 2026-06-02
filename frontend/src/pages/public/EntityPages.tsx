/**
 * Static entity pages — About, Press, Careers, Contact, Trust, Help,
 * Privacy, Terms. One file, eight exported components. Each declares its
 * own <SEO> block with appropriate schema (Article / ContactPage / etc.).
 *
 * The content here is the minimum-viable copy that gets the URLs indexed
 * without thin-content penalties; flesh out individual pages over time
 * without re-architecting.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { SEO } from '../../seo/SEO';
import { article, breadcrumbList, SITE_ORIGIN } from '../../seo/schema';


const Shell: React.FC<{
    title: string;
    description: string;
    canonical: string;
    schema: object | object[];
    children: React.ReactNode;
}> = ({ title, description, canonical, schema, children }) => (
    <>
        <SEO title={title} description={description} canonical={canonical} schema={schema} />
        <article className="max-w-3xl mx-auto px-4 sm:px-6 py-16 prose prose-indigo prose-headings:font-bold">
            {children}
            <hr className="my-12 border-gray-200" />
            <p className="text-sm text-gray-500">
                Have a question? <Link to="/contact" className="text-indigo-700">Contact us</Link> or browse the{' '}
                <Link to="/" className="text-indigo-700">homepage</Link>.
            </p>
        </article>
    </>
);

const baseCrumbs = (name: string, url: string) => breadcrumbList([
    { name: 'mySpace', url: SITE_ORIGIN },
    { name, url },
]);


// ---------- About --------------------------------------------------------

export const AboutPage: React.FC = () => {
    const url = `${SITE_ORIGIN}/about`;
    return (
        <Shell
            title="About mySpace"
            description="mySpace is India's discovery and booking platform for reading rooms, study cabins, PGs, hostels, and co-working spaces — built for students and working professionals."
            canonical={url}
            schema={[
                baseCrumbs('About', url),
                article({
                    headline: 'About mySpace',
                    description: 'How mySpace works and why we built it.',
                    url,
                    image: `${SITE_ORIGIN}/logo_stacked.png`,
                    datePublished: '2026-01-01',
                }),
            ]}
        >
            <h1>About mySpace</h1>
            <p className="lead">
                mySpace is India's discovery and booking platform for reading rooms, study cabins, PGs,
                hostels, co-working and co-learning spaces. We connect verified owners with students
                and working professionals across every city.
            </p>

            <h2>Why mySpace exists</h2>
            <p>
                Finding a reading room, PG or hostel in India has historically meant calling brokers,
                WhatsApp groups, and word of mouth. Listings were unverified, prices opaque, and
                booking required visiting in person. mySpace fixes that by bringing every space into
                one searchable, verified marketplace — with transparent pricing and instant online
                booking.
            </p>

            <h2>What we cover</h2>
            <p>
                We list reading rooms, study cabins (private and shared), PGs, hostels, co-working
                spaces, co-learning spaces, rental houses, and rooms for rent. We're nationwide from
                day one — supply launches city by city, starting with Kerala.
            </p>

            <h2>How verification works</h2>
            <p>
                Every owner submits identity and address proof. Our team reviews each property before
                publishing. Listings that fall below quality thresholds are paused. Reviews and ratings
                from real students and professionals shape what's visible.
            </p>
        </Shell>
    );
};

// ---------- Press --------------------------------------------------------

export const PressPage: React.FC = () => {
    const url = `${SITE_ORIGIN}/press`;
    return (
        <Shell
            title="Press &amp; Media"
            description="Press resources, brand assets, and media inquiries for mySpace."
            canonical={url}
            schema={baseCrumbs('Press', url)}
        >
            <h1>Press &amp; Media</h1>
            <p>For press inquiries, partnerships and brand assets, reach us at <a href="mailto:press@myspaceapp.in">press@myspaceapp.in</a>.</p>
            <h2>Brand assets</h2>
            <p>Download the mySpace logo, wordmark, and screenshots. Please don't alter the marks or use them to imply endorsement.</p>
            <h2>Latest news</h2>
            <p>Coverage and announcements will appear here as the platform expands.</p>
        </Shell>
    );
};

// ---------- Careers ------------------------------------------------------

export const CareersPage: React.FC = () => {
    const url = `${SITE_ORIGIN}/careers`;
    return (
        <Shell
            title="Careers at mySpace"
            description="Open roles at mySpace — we're hiring across engineering, design, content, and growth."
            canonical={url}
            schema={baseCrumbs('Careers', url)}
        >
            <h1>Careers at mySpace</h1>
            <p>We're building the operating system for India's accommodation marketplace. Open roles are listed below; for everything else, write to <a href="mailto:careers@myspaceapp.in">careers@myspaceapp.in</a>.</p>
            <h2>Open positions</h2>
            <p>Roles will be published here. Until then, send a short note and a link to your work.</p>
        </Shell>
    );
};

// ---------- Contact ------------------------------------------------------

export const ContactPage: React.FC = () => {
    const url = `${SITE_ORIGIN}/contact`;
    return (
        <Shell
            title="Contact mySpace"
            description="Reach the mySpace team — support, partnerships, owner listings, and feedback."
            canonical={url}
            schema={baseCrumbs('Contact', url)}
        >
            <h1>Contact us</h1>
            <ul>
                <li><strong>Support:</strong> <a href="mailto:support@myspaceapp.in">support@myspaceapp.in</a></li>
                <li><strong>Owner listings:</strong> <a href="mailto:list@myspaceapp.in">list@myspaceapp.in</a></li>
                <li><strong>Partnerships:</strong> <a href="mailto:partners@myspaceapp.in">partners@myspaceapp.in</a></li>
                <li><strong>Press:</strong> <a href="mailto:press@myspaceapp.in">press@myspaceapp.in</a></li>
            </ul>
        </Shell>
    );
};

// ---------- Trust --------------------------------------------------------

export const TrustPage: React.FC = () => {
    const url = `${SITE_ORIGIN}/trust`;
    return (
        <Shell
            title="Trust &amp; Safety"
            description="How mySpace verifies owners and protects renters."
            canonical={url}
            schema={baseCrumbs('Trust', url)}
        >
            <h1>Trust &amp; Safety</h1>
            <p>mySpace is built on three trust pillars:</p>
            <ol>
                <li><strong>Owner verification</strong> — every owner submits identity, address proof, and bank details before any listing goes live.</li>
                <li><strong>Listing review</strong> — our team checks photos, amenities, and pricing for accuracy.</li>
                <li><strong>Secure payments</strong> — all bookings flow through Razorpay with full GST invoicing.</li>
            </ol>
            <p>If something feels off, report a listing from the listing page or write to <a href="mailto:trust@myspaceapp.in">trust@myspaceapp.in</a>.</p>
        </Shell>
    );
};

// ---------- Help ---------------------------------------------------------

export const HelpPage: React.FC = () => {
    const url = `${SITE_ORIGIN}/help`;
    return (
        <Shell
            title="Help Center"
            description="Answers to common questions about mySpace bookings, listings, payments, and refunds."
            canonical={url}
            schema={baseCrumbs('Help', url)}
        >
            <h1>Help Center</h1>
            <h2>For renters</h2>
            <p>How to search, book, and manage your stays.</p>
            <h2>For owners</h2>
            <p>How to list, manage listings, and get paid.</p>
            <h2>Payments &amp; refunds</h2>
            <p>How payments work, escrow timing, and refund policy.</p>
            <p>Still stuck? Email <a href="mailto:support@myspaceapp.in">support@myspaceapp.in</a>.</p>
        </Shell>
    );
};

// ---------- Privacy ------------------------------------------------------

export const PrivacyPage: React.FC = () => {
    const url = `${SITE_ORIGIN}/privacy`;
    return (
        <Shell
            title="Privacy Policy"
            description="How mySpace collects, uses, and protects your personal data — DPDP compliant."
            canonical={url}
            schema={baseCrumbs('Privacy', url)}
        >
            <h1>Privacy Policy</h1>
            <p><em>Last updated: {new Date().getFullYear()}.</em></p>
            <p>mySpace operates under the Digital Personal Data Protection Act (DPDP), 2023. We collect only what we need to provide and improve the service: account info, search and booking history, communications you opt into.</p>
            <h2>What we collect</h2>
            <p>Account information, browsing &amp; booking history, payment details (handled by Razorpay), and the communications you choose to receive.</p>
            <h2>What we don't do</h2>
            <p>We never sell your data. We never share individual user data with property owners — owners only see aggregated metrics about their listings.</p>
            <h2>Your rights</h2>
            <p>You can request export or deletion of your data at any time from <Link to="/student/privacy">Privacy Settings</Link> when logged in, or by emailing <a href="mailto:privacy@myspaceapp.in">privacy@myspaceapp.in</a>.</p>
        </Shell>
    );
};

// ---------- Terms --------------------------------------------------------

export const TermsPage: React.FC = () => {
    const url = `${SITE_ORIGIN}/terms`;
    return (
        <Shell
            title="Terms of Service"
            description="The terms governing your use of mySpace as a renter or owner."
            canonical={url}
            schema={baseCrumbs('Terms', url)}
        >
            <h1>Terms of Service</h1>
            <p><em>Last updated: {new Date().getFullYear()}.</em></p>
            <p>By using mySpace you agree to the terms below. We may update these terms; we'll notify you of material changes via email.</p>
            <h2>Using the service</h2>
            <p>You must be 18 or older. Don't misuse the service; don't try to interfere with how it works.</p>
            <h2>Bookings</h2>
            <p>Bookings made through mySpace are between you and the listing owner. mySpace facilitates the booking and payment.</p>
            <h2>Owner responsibilities</h2>
            <p>Owners must keep listings accurate and respond to inquiries in a timely fashion.</p>
            <h2>Liability</h2>
            <p>mySpace is not liable for off-platform agreements or for issues arising from owner misrepresentation we couldn't have caught.</p>
        </Shell>
    );
};
