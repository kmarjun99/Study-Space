
import React, { useState } from 'react';

type LogoVariant = 'sidebar' | 'header' | 'auth' | 'icon';

interface LogoProps {
    variant?: LogoVariant;
    className?: string;
}

// Logo strategy: serve the static PNG bundled with the SPA at
// `/myspace_logo.png` from `frontend/public/`. This used to route through
// the backend `/img/?w=N&fmt=webp` transform pipeline, but that depends on
// the backend container having the file in its uploads/ directory AND on
// Cloudflare not having cached a 404 from a moment when it didn't — both
// of which kept biting us in prod (logo 404 on owner / student pages even
// though the static asset was always present at /myspace_logo.png).
//
// Tradeoff: the static PNG is ~2 MB and gets served full-size to first-time
// visitors. Browsers cache it for a year (`Cache-Control: immutable` from
// the static-asset nginx location), so repeat visits are free. If file size
// becomes an issue, optimise the PNG itself (e.g. tinypng) — keep the
// component dead-simple.
//
// The `?v=3` cache-buster is bumped whenever the asset changes — it forces
// browsers (and Cloudflare) to re-fetch instead of using a cached 404 from
// an earlier broken deploy.
const LOGO_URL = '/myspace_logo.png?v=3';

export const Logo: React.FC<LogoProps> = ({ variant = 'header', className = '' }) => {
    // If the image fails to load (e.g. broken cache, missing file on a fresh
    // deploy), fall back to a wordmark so the chrome never looks empty.
    const [failed, setFailed] = useState(false);

    const Wordmark = (
        <span className="font-bold tracking-tight text-indigo-700">mySpace</span>
    );

    const commonProps = {
        src: LOGO_URL,
        alt: 'mySpace',
        decoding: 'async' as const,
        onError: () => setFailed(true),
    };

    switch (variant) {
        case 'sidebar':
            return (
                <div className={`flex items-center justify-center ${className}`}>
                    {failed ? Wordmark : <img {...commonProps} className="h-10 w-auto object-contain" />}
                </div>
            );

        case 'header':
            return (
                <div className={`flex items-center justify-center ${className}`}>
                    {failed ? Wordmark : <img {...commonProps} className="h-12 w-auto object-contain" />}
                </div>
            );

        case 'auth':
            return (
                <div className={`text-center ${className}`}>
                    {failed
                        ? <span className="block text-3xl font-bold tracking-tight text-indigo-700">mySpace</span>
                        : <img {...commonProps} className="mx-auto h-32 w-auto object-contain" />}
                </div>
            );

        case 'icon':
            return failed
                ? <span className={`text-xs font-bold text-indigo-700 ${className}`}>MS</span>
                : <img {...commonProps} className={`h-8 w-8 object-contain ${className}`} />;

        default:
            return null;
    }
};
