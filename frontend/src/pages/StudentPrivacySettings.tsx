/**
 * Student-facing privacy & consent settings.
 *
 * Every flag defaults OFF (opt-in policy). Toggling a flag persists and
 * stamps the current policy version. The "Delete all my data" button calls
 * the right-to-erasure endpoint and wipes the local anonymous session id.
 *
 * Layered controls:
 *   - Analytics tracking          — gates the entire behavioral event firehose
 *   - Personalized recommendations — gates use of behavior for "for me" surfaces
 *   - Marketing notifications      — in-app + email nudges
 *   - WhatsApp updates             — separate because of regulatory weight
 *   - Location-based suggestions   — separate because of data sensitivity
 *
 * The page is intentionally text-heavy so the user knows exactly what each
 * flag does. Privacy UX where the user doesn't understand the choices is
 * worse than no choice at all.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button } from '../components/UI';
import { ArrowLeft, ShieldCheck, AlertTriangle, Trash2 } from 'lucide-react';
import {
    consentService, ConsentPreferences, ConsentUpdate,
} from '../services/consentService';
import { eventService } from '../services/eventService';

// Bump this when the privacy policy text changes meaningfully.
const POLICY_VERSION = '2026-05';

interface ToggleProps {
    label: string;
    description: string;
    checked: boolean;
    onChange: (value: boolean) => void;
    disabled?: boolean;
    severity?: 'normal' | 'sensitive';
}

const Toggle: React.FC<ToggleProps> = ({
    label, description, checked, onChange, disabled, severity = 'normal',
}) => (
    <div className={`flex items-start justify-between gap-4 py-4 border-t border-gray-100`}>
        <div className="flex-1">
            <div className="flex items-center gap-2">
                <span className="font-medium text-gray-900">{label}</span>
                {severity === 'sensitive' && (
                    <span className="text-xs px-2 py-0.5 bg-amber-50 text-amber-700 rounded">sensitive</span>
                )}
            </div>
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">{description}</p>
        </div>
        <button
            type="button"
            disabled={disabled}
            onClick={() => onChange(!checked)}
            className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full transition-colors ${checked ? 'bg-indigo-600' : 'bg-gray-200'
                } ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
            aria-pressed={checked}
            aria-label={label}
        >
            <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'
                    } mt-0.5`}
            />
        </button>
    </div>
);

export const StudentPrivacySettings: React.FC = () => {
    const navigate = useNavigate();
    const [prefs, setPrefs] = useState<ConsentPreferences | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [erasing, setErasing] = useState(false);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const c = await consentService.get();
                if (!cancelled) setPrefs(c);
            } catch (e: any) {
                if (!cancelled) {
                    setError(e?.response?.status === 404
                        ? 'Privacy settings are not enabled on this server yet.'
                        : (e?.response?.data?.detail || 'Could not load preferences.'));
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const persist = async (patch: ConsentUpdate, key: string) => {
        if (!prefs) return;
        setSaving(key);
        try {
            const updated = await consentService.update({
                ...patch,
                consent_policy_version: POLICY_VERSION,
            });
            setPrefs(updated);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not save.');
        } finally {
            setSaving(null);
        }
    };

    const revokeAll = async () => {
        if (!confirm('Turn off all personalization, marketing, and tracking? You can re-enable any time.')) return;
        setSaving('revoke');
        try {
            const updated = await consentService.revokeAll();
            setPrefs(updated);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not revoke.');
        } finally {
            setSaving(null);
        }
    };

    const deleteEverything = async () => {
        if (!confirm(
            'Delete every behavioral event mySpace has on you?\n\n' +
            'This does not delete bookings, payments, or invoices — only behavioral analytics. ' +
            'Action is permanent and cannot be reversed.',
        )) return;
        setErasing(true);
        try {
            const res = await eventService.deleteMyEvents();
            alert(`Deleted ${res.deleted.toLocaleString()} event records. Your anonymous session has also been reset.`);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not delete events.');
        } finally {
            setErasing(false);
        }
    };

    if (loading) return <div className="p-6 text-gray-500">Loading…</div>;
    if (error) return <Card className="m-6 p-4 border-red-200 bg-red-50 text-red-700 text-sm">{error}</Card>;
    if (!prefs) return null;

    return (
        <div className="max-w-3xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>

            <div className="flex items-start gap-3 mb-4">
                <ShieldCheck className="w-6 h-6 text-indigo-600 flex-shrink-0 mt-1" />
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Privacy &amp; Personalization</h1>
                    <p className="text-gray-500 text-sm">
                        Decide what mySpace can learn from your behavior, and how we can
                        reach out to you. Defaults are conservative — turn things on only
                        where you find them useful.
                    </p>
                </div>
            </div>

            <Card className="p-4 mb-4 bg-amber-50 border-amber-200">
                <div className="flex items-start gap-2 text-sm text-amber-900">
                    <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <div>
                        With analytics tracking <strong>off</strong>, mySpace can't learn what listings you
                        prefer — your recommendations will be generic. This page never affects your
                        bookings, payments, or invoices.
                    </div>
                </div>
            </Card>

            <Card className="p-6 mb-4">
                <h2 className="font-semibold text-gray-900 mb-1">Behavioral analytics</h2>
                <p className="text-xs text-gray-500 mb-2">
                    Master switch for tracking what you search, view, and save inside the app.
                </p>
                <Toggle
                    label="Allow analytics tracking"
                    description="Without this, mySpace records nothing about your in-app behavior. Booking confirmations and payment receipts are kept separately and are not affected."
                    checked={prefs.allow_analytics_tracking}
                    onChange={v => persist({ allow_analytics_tracking: v }, 'analytics')}
                    disabled={saving !== null}
                />
                <Toggle
                    label="Personalized recommendations"
                    description="Use your search and view history to recommend listings you may like. Requires analytics tracking to be on."
                    checked={prefs.allow_personalized_recommendations}
                    onChange={v => persist({ allow_personalized_recommendations: v }, 'reco')}
                    disabled={saving !== null || !prefs.allow_analytics_tracking}
                />
            </Card>

            <Card className="p-6 mb-4">
                <h2 className="font-semibold text-gray-900 mb-1">Communications</h2>
                <p className="text-xs text-gray-500 mb-2">
                    Choose how we may reach out to you. Booking-related transactional
                    messages always go through regardless of these settings.
                </p>
                <Toggle
                    label="Marketing notifications"
                    description="In-app, push, and email nudges (e.g., reminders to complete a booking, special offers, new listings near you)."
                    checked={prefs.allow_marketing_notifications}
                    onChange={v => persist({ allow_marketing_notifications: v }, 'marketing')}
                    disabled={saving !== null}
                />
                <Toggle
                    label="WhatsApp updates"
                    severity="sensitive"
                    description="Recommendations and follow-ups via WhatsApp. Separate from marketing notifications because WhatsApp messages cost us money and are regulated more strictly."
                    checked={prefs.allow_whatsapp_updates}
                    onChange={v => persist({ allow_whatsapp_updates: v }, 'whatsapp')}
                    disabled={saving !== null}
                />
            </Card>

            <Card className="p-6 mb-4">
                <h2 className="font-semibold text-gray-900 mb-1">Location</h2>
                <Toggle
                    label="Location-based suggestions"
                    severity="sensitive"
                    description="Use your approximate location to surface nearby listings and 'near my college' suggestions. Off by default."
                    checked={prefs.allow_location_based_suggestions}
                    onChange={v => persist({ allow_location_based_suggestions: v }, 'location')}
                    disabled={saving !== null}
                />
            </Card>

            <Card className="p-6 mb-4 border-red-200">
                <h2 className="font-semibold text-gray-900 mb-1">Data controls</h2>
                <p className="text-xs text-gray-500 mb-3">
                    Granular control over what mySpace stores about you.
                </p>
                <div className="flex flex-col sm:flex-row gap-2">
                    <Button variant="outline" size="sm" onClick={revokeAll} isLoading={saving === 'revoke'}>
                        Turn everything off
                    </Button>
                    <Button variant="outline" size="sm" onClick={deleteEverything} isLoading={erasing}>
                        <Trash2 className="w-3 h-3 mr-1" /> Delete all my behavioral data
                    </Button>
                </div>
                <p className="text-xs text-gray-400 mt-2">
                    Deletion removes behavioral events only. Your account, bookings, payments,
                    and invoices remain untouched — those are subject to a separate retention
                    policy as required by Indian tax law.
                </p>
            </Card>

            <p className="text-xs text-gray-400 text-center mt-6">
                Current policy version: <code>{prefs.consent_policy_version || '—'}</code>
            </p>
        </div>
    );
};

export default StudentPrivacySettings;
