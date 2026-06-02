/**
 * Reusable feature-flag banner for intelligence/analytics module pages.
 *
 * Surfaces the current state of a `tax_config` boolean flag and lets a
 * super-admin flip it inline — instead of forcing them to hunt for the
 * switch on the Tax Config screen. Reads/writes the existing tax-config
 * endpoints, so there is no module-specific backend to maintain.
 *
 * Reads are available to any admin; the toggle write is super-admin only
 * (enforced by the backend — non-super-admins get a clear error).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Power } from 'lucide-react';
import { taxConfigService } from '../services/taxConfigService';
import { Badge } from './UI';

interface FeatureFlagToggleProps {
    flagKey: string;
    label: string;
    /** What turning this on actually does — shown under the title. */
    description?: string;
    /** Called after a successful toggle so the host page can refetch data. */
    onChange?: (enabled: boolean) => void;
}

export const FeatureFlagToggle: React.FC<FeatureFlagToggleProps> = ({
    flagKey, label, description, onChange,
}) => {
    const [enabled, setEnabled] = useState<boolean | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setError(null);
        try {
            const items = await taxConfigService.list();
            const item = items.find(i => i.key === flagKey);
            // Missing row = flag has never been set = OFF (matches backend default).
            setEnabled(item ? Boolean(item.value) : false);
        } catch {
            setError('Could not read the current flag state.');
        }
    }, [flagKey]);

    useEffect(() => { void load(); }, [load]);

    const toggle = async () => {
        if (enabled === null) return;
        const next = !enabled;
        if (!confirm(
            next
                ? `Enable "${label}"?`
                : `Disable "${label}"? Existing data is preserved; the module stops doing new work until re-enabled.`,
        )) return;
        setBusy(true);
        try {
            await taxConfigService.upsert(flagKey, next);
            setEnabled(next);
            onChange?.(next);
        } catch (e: any) {
            alert(
                e?.response?.data?.detail ||
                'Could not change the flag. This action is super-admin only.',
            );
        } finally {
            setBusy(false);
        }
    };

    const on = enabled === true;

    return (
        <div className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 mb-4 ${
            enabled === null
                ? 'border-gray-200 bg-gray-50'
                : on
                    ? 'border-green-200 bg-green-50/50'
                    : 'border-amber-200 bg-amber-50/50'
        }`}>
            <div className="flex items-center gap-3 min-w-0">
                <div className={`rounded-lg p-2 flex-shrink-0 ${
                    on ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                }`}>
                    <Power className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-gray-900">{label}</span>
                        {enabled === null ? (
                            <span className="text-xs text-gray-400">checking…</span>
                        ) : (
                            <Badge variant={on ? 'success' : 'warning'}>{on ? 'ENABLED' : 'DISABLED'}</Badge>
                        )}
                    </div>
                    <p className="text-xs text-gray-500 truncate">
                        {description ? `${description} · ` : ''}
                        <code className="text-[11px] bg-gray-100 px-1 rounded">{flagKey}</code>
                    </p>
                    {error && <p className="text-xs text-red-600 mt-0.5">{error}</p>}
                </div>
            </div>

            <button
                onClick={toggle}
                disabled={enabled === null || busy}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
                    on ? 'bg-green-500' : 'bg-gray-300'
                }`}
                aria-pressed={on}
                aria-label={`${on ? 'Disable' : 'Enable'} ${label}`}
                title={`${on ? 'Disable' : 'Enable'} ${label}`}
            >
                <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
                    on ? 'translate-x-5' : 'translate-x-1'
                }`} />
            </button>
        </div>
    );
};

export default FeatureFlagToggle;
