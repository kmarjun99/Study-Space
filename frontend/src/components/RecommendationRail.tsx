/**
 * Generic horizontal recommendation rail.
 *
 * Wraps the four surfaces (for-you / similar / trending / recently-viewed)
 * behind one component. Fetches on mount, hides itself silently when there
 * are no results (so users with consent off see no broken UI).
 *
 * Click navigates to the appropriate detail page. We don't fire an explicit
 * "ad.clicked" event here — that's wired at the destination page in Phase 4.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Badge } from './UI';
import { Sparkles, TrendingUp, History, ChevronRight } from 'lucide-react';
import {
    recommendationService, Recommendation,
} from '../services/recommendationService';

type Surface = 'for-me' | 'similar' | 'trending' | 'recently-viewed';

interface Props {
    surface: Surface;
    // For 'similar' only:
    similarTo?: { type: 'reading_room' | 'accommodation'; id: string };
    // For 'trending' only:
    city?: string;
    limit?: number;
    title?: string;
}

const surfaceIcon: Record<Surface, React.ReactNode> = {
    'for-me': <Sparkles className="w-4 h-4 text-indigo-600" />,
    'similar': <ChevronRight className="w-4 h-4 text-indigo-600" />,
    'trending': <TrendingUp className="w-4 h-4 text-amber-600" />,
    'recently-viewed': <History className="w-4 h-4 text-gray-600" />,
};

const defaultTitle: Record<Surface, string> = {
    'for-me': 'Recommended for you',
    'similar': 'Similar listings',
    'trending': 'Trending nearby',
    'recently-viewed': 'Continue where you left off',
};

const formatINR = (n: number | null) =>
    n === null ? '—' : n.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });

export const RecommendationRail: React.FC<Props> = ({
    surface, similarTo, city, limit = 10, title,
}) => {
    const navigate = useNavigate();
    const [items, setItems] = useState<Recommendation[] | null>(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            let recs: Recommendation[] = [];
            try {
                if (surface === 'for-me') {
                    recs = await recommendationService.forMe(limit);
                } else if (surface === 'similar' && similarTo) {
                    recs = await recommendationService.similar(similarTo.type, similarTo.id, limit);
                } else if (surface === 'trending') {
                    recs = await recommendationService.trending(city, 7, limit);
                } else if (surface === 'recently-viewed') {
                    recs = await recommendationService.recentlyViewed(limit);
                }
            } catch {
                recs = [];
            }
            if (!cancelled) setItems(recs);
        })();
        return () => { cancelled = true; };
    }, [surface, similarTo?.type, similarTo?.id, city, limit]);

    // Hide entirely when the backend returned nothing — keeps the UI clean
    // for users who haven't opted in to recommendations.
    if (items === null) return null;
    if (items.length === 0) return null;

    const navigateTo = (r: Recommendation) => {
        if (r.listing_type === 'reading_room') {
            navigate(`/student/reading-room/${r.listing_id}`);
        } else {
            navigate(`/student/accommodation/${r.listing_id}`);
        }
    };

    return (
        <div className="my-6">
            <div className="flex items-center gap-2 mb-3">
                {surfaceIcon[surface]}
                <h3 className="font-semibold text-gray-900">{title || defaultTitle[surface]}</h3>
            </div>
            <div className="flex gap-4 overflow-x-auto pb-2 -mx-2 px-2">
                {items.map(r => (
                    <Card
                        key={`${r.listing_type}-${r.listing_id}`}
                        className="p-4 min-w-[220px] max-w-[260px] flex-shrink-0 cursor-pointer hover:shadow-md transition-shadow"
                        onClick={() => navigateTo(r)}
                    >
                        <div className="flex items-start justify-between gap-2 mb-2">
                            <span className="font-medium text-gray-900 line-clamp-2">{r.name}</span>
                            {r.extra.is_sponsored && (
                                <Badge variant="warning" className="text-[10px]">Sponsored</Badge>
                            )}
                        </div>
                        {r.city && (
                            <p className="text-xs text-gray-500">{r.city}{r.state && `, ${r.state}`}</p>
                        )}
                        {r.price !== null && (
                            <p className="text-sm font-semibold text-indigo-600 mt-2">
                                {formatINR(r.price)}<span className="text-xs text-gray-400">/mo</span>
                            </p>
                        )}
                        <p className="text-[10px] text-gray-400 mt-2 truncate" title={r.reason_code}>
                            {r.reason_code.replace(/_/g, ' ')}
                        </p>
                    </Card>
                ))}
            </div>
        </div>
    );
};

export default RecommendationRail;
