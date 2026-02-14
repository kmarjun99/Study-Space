
import React from 'react';

type LogoVariant = 'sidebar' | 'header' | 'auth' | 'icon';

interface LogoProps {
    variant?: LogoVariant;
    className?: string;
}

export const Logo: React.FC<LogoProps> = ({ variant = 'header', className = '' }) => {
    // Asset Paths (Centralized)
    const ASSETS = {
        ICON: '/profile_favicon.png', // Square Icon
        STACKED: '/logo_stacked.png', // Vertical Stacked
    };

    switch (variant) {
        case 'sidebar':
            // Square icon only, compact
            return (
                <div className={`flex items-center justify-center ${className}`}>
                    <img
                        src={ASSETS.ICON}
                        alt="StudySpace"
                        className="h-10 w-10 object-contain"
                    />
                </div>
            );

        case 'header':
            // Icon + Text Stacked (Compact for mobile headers or top navs)
            return (
                <div className={`flex flex-col items-center justify-center ${className}`}>
                    <img
                        src={ASSETS.STACKED}
                        alt="StudySpace"
                        className="h-12 w-auto object-contain"
                    />
                </div>
            );



        case 'auth':
            // Large Stacked Logo for Login/Signup
            return (
                <div className={`text-center ${className}`}>
                    <img
                        src={ASSETS.STACKED}
                        alt="StudySpace"
                        className="mx-auto h-24 w-auto object-contain"
                    />
                </div>
            );

        case 'icon':
            // Raw Icon for other uses (Profiles, etc.)
            return (
                <img
                    src={ASSETS.ICON}
                    alt="StudySpace Logo"
                    className={`object-contain ${className}`}
                />
            );

        default:
            return null;
    }
};
