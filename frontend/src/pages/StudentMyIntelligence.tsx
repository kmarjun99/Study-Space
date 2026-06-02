/**
 * Student transparency surface — "what has mySpace inferred about me?".
 *
 * Returns null gracefully if no profile has been built yet. The user can
 * also turn off personalization from Privacy Settings; the link is shown
 * at the bottom of this page.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Badge } from '../components/UI';
import { ArrowLeft, Sparkles, AlertCircle, Info } from 'lucide-react';
import {
    intelligenceService, IntelligenceProfile,
} from '../services/intelligenceService';

const pct = (n: number) => `${Math.round(n * 100)}%`;
const formatINR = (n: number | null) =>
    n === null ? '—' : n.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });

export const StudentMyIntelligence: React.FC = () => {
    const navigate = useNavigate();
    const [profile, setProfile] = useState<IntelligenceProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const p = await intelligenceService.getMyProfile();
                if (!cancelled) setProfile(p);
            } catch (e: any) {
                if (!cancelled) {
                    setError(e?.response?.data?.detail ||
                        'Could not load your intelligence profile.');
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    if (loading) return <div className="p-6 text-gray-500">Loading…</div>;

    if (error) {
        return (
            <Card className="m-6 p-4 border-amber-200 bg-amber-50 text-sm text-amber-800">
                {error}
            </Card>
        );
    }

    return (
        <div className="max-w-3xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <div className="flex items-start gap-3 mb-4">
                <Sparkles className="w-6 h-6 text-indigo-600 flex-shrink-0 mt-1" />
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">What mySpace has learned</h1>
                    <p className="text-gray-500 text-sm">
                        This is the profile we've derived from your behavior. It's used to
                        personalize listing recommendations when you've opted in.
                    </p>
                </div>
            </div>

            {!profile ? (
                <Card className="p-8 text-center text-gray-500">
                    <Info className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                    <p className="font-medium">No profile yet.</p>
                    <p className="text-sm mt-1">
                        Either you haven't searched / viewed enough listings yet, or
                        you've not opted in to personalized recommendations. Visit
                        <button
                            className="text-indigo-600 mx-1 underline"
                            onClick={() => navigate('/student/privacy')}
                        >
                            Privacy Settings
                        </button>
                        to change either.
                    </p>
                </Card>
            ) : (
                <>
                    <Card className="p-6 mb-4">
                        <div className="flex items-center justify-between mb-3">
                            <h2 className="font-semibold text-gray-900">Current intent</h2>
                            <Badge variant={
                                profile.intent_level === 'HOT_LEAD' ? 'error'
                                    : profile.intent_level === 'HIGH_INTENT' ? 'warning'
                                        : 'info'
                            }>
                                {profile.intent_level}
                            </Badge>
                        </div>
                        <div className="grid grid-cols-2 gap-y-2 text-sm">
                            <div className="text-gray-500">Confidence in this profile</div>
                            <div className="text-gray-900">{pct(profile.profile_confidence_score)}</div>
                            <div className="text-gray-500">Events used to build it</div>
                            <div className="text-gray-900">{profile.event_count}</div>
                            <div className="text-gray-500">Last active</div>
                            <div className="text-gray-900">
                                {profile.last_active_at ? new Date(profile.last_active_at).toLocaleString('en-IN') : '—'}
                            </div>
                        </div>
                    </Card>

                    <Card className="p-6 mb-4">
                        <h2 className="font-semibold text-gray-900 mb-3">Inferred preferences</h2>
                        <div className="grid grid-cols-2 gap-y-2 text-sm">
                            <div className="text-gray-500">City</div>
                            <div className="text-gray-900">{profile.preferred_city || '—'}</div>
                            <div className="text-gray-500">Locations</div>
                            <div className="text-gray-900">
                                {profile.preferred_locations.length > 0 ? profile.preferred_locations.join(', ') : '—'}
                            </div>
                            <div className="text-gray-500">Property types</div>
                            <div className="text-gray-900">
                                {profile.preferred_property_types.length > 0 ? profile.preferred_property_types.join(', ') : '—'}
                            </div>
                            <div className="text-gray-500">Amenities</div>
                            <div className="text-gray-900">
                                {profile.preferred_amenities.length > 0 ? profile.preferred_amenities.join(', ') : '—'}
                            </div>
                            <div className="text-gray-500">Price band</div>
                            <div className="text-gray-900">
                                {formatINR(profile.preferred_price_min)} – {formatINR(profile.preferred_price_max)}
                            </div>
                        </div>
                    </Card>

                    <Card className="p-6 mb-4">
                        <h2 className="font-semibold text-gray-900 mb-3">Behavior scores</h2>
                        <div className="grid grid-cols-2 gap-y-2 text-sm">
                            <div className="text-gray-500">Booking urgency</div>
                            <div className="text-gray-900">{pct(profile.booking_urgency_score)}</div>
                            <div className="text-gray-500">Budget sensitivity</div>
                            <div className="text-gray-900">{pct(profile.budget_sensitivity_score)}</div>
                            <div className="text-gray-500">Location sensitivity</div>
                            <div className="text-gray-900">{pct(profile.location_sensitivity_score)}</div>
                            <div className="text-gray-500">Premium interest</div>
                            <div className="text-gray-900">{pct(profile.premium_interest_score)}</div>
                            <div className="text-gray-500">Cancellation risk</div>
                            <div className="text-gray-900">{pct(profile.cancellation_risk_score)}</div>
                            <div className="text-gray-500">Conversion probability</div>
                            <div className="text-gray-900">{pct(profile.conversion_probability_score)}</div>
                        </div>
                    </Card>
                </>
            )}

            <Card className="p-4 border-gray-200 bg-gray-50 text-xs text-gray-600">
                <div className="flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <div>
                        Profile rebuilds nightly from your last 90 days of activity. You can
                        delete the underlying event data or opt out of personalization any
                        time in
                        <button
                            className="text-indigo-600 mx-1 underline"
                            onClick={() => navigate('/student/privacy')}
                        >
                            Privacy Settings
                        </button>.
                    </div>
                </div>
            </Card>
        </div>
    );
};

export default StudentMyIntelligence;
