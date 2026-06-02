/**
 * Super-admin notification automation page (Phase 4C).
 *
 * Rule list + create form + per-rule evaluate / pause / deliveries view +
 * a "Dispatch pending now" button that flushes the QUEUED backlog.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ArrowLeft, RefreshCw, Plus, Play, Send, AlertCircle, Zap,
    Power, Activity, Clock, CheckCircle, XCircle, AlertTriangle,
} from 'lucide-react';
import { Card, Button, Badge } from '../components/UI';
import {
    notificationRuleService, NotificationRule, RuleInput, TriggerType,
    RuleDelivery, AutomationStatus,
} from '../services/notificationRuleService';
import type { CampaignChannel } from '../services/campaignService';

const TRIGGERS: TriggerType[] = [
    'BOOKING_ABANDONED',
    'REPEAT_SEARCH_NO_BOOKING',
    'AVAILABILITY_CHECKED_NO_BOOKING',
    'PAYMENT_FAILED',
];
const CHANNELS: CampaignChannel[] = ['IN_APP', 'EMAIL', 'PUSH', 'WHATSAPP'];

const triggerLabel: Record<TriggerType, string> = {
    BOOKING_ABANDONED: 'Booking started but not completed',
    REPEAT_SEARCH_NO_BOOKING: 'Repeated searches, no booking',
    AVAILABILITY_CHECKED_NO_BOOKING: 'Availability checked, no booking',
    PAYMENT_FAILED: 'Payment failed recently',
};

const HealthStat: React.FC<{
    icon: React.ReactNode;
    label: string;
    value: string;
    tone: 'good' | 'bad' | 'warn' | 'neutral';
}> = ({ icon, label, value, tone }) => {
    const toneClass = {
        good: 'text-green-700',
        bad: 'text-red-700',
        warn: 'text-amber-700',
        neutral: 'text-gray-800',
    }[tone];
    return (
        <div className="rounded-lg bg-white border border-gray-200 px-3 py-2">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-gray-500 uppercase tracking-wide">
                {icon}
                {label}
            </div>
            <div className={`mt-1 text-lg font-bold leading-none ${toneClass}`}>{value}</div>
        </div>
    );
};

export const SuperAdminNotificationRules: React.FC = () => {
    const navigate = useNavigate();
    const [rules, setRules] = useState<NotificationRule[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState<string | null>(null);

    const [showCreate, setShowCreate] = useState(false);
    const [draft, setDraft] = useState<RuleInput>({
        slug: '', name: '', body_template: 'Hi {{first_name}}, ',
        subject_template: 'mySpace nudge',
        trigger_type: 'BOOKING_ABANDONED',
        trigger_window_minutes: 120,
        min_event_count: 1,
        channel: 'IN_APP',
        cooldown_hours: 24,
        frequency_cap_per_user: 3,
        frequency_cap_window_days: 7,
        is_active: false,
    });

    const [selected, setSelected] = useState<NotificationRule | null>(null);
    const [deliveries, setDeliveries] = useState<RuleDelivery[] | null>(null);

    const [status, setStatus] = useState<AutomationStatus | null>(null);
    const [togglingAutomation, setTogglingAutomation] = useState(false);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [rs, st] = await Promise.all([
                notificationRuleService.list(true),
                notificationRuleService.automationStatus().catch(() => null),
            ]);
            setRules(rs);
            setStatus(st);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load rules.');
        } finally {
            setLoading(false);
        }
    }, []);

    const handleToggleAutomation = async () => {
        if (!status) return;
        const next = !status.enabled;
        if (!confirm(
            next
                ? 'Enable notification automation?\n\nThe scheduler will evaluate active rules and dispatch queued notifications every 30 minutes.'
                : 'Disable notification automation?\n\nRule evaluation and dispatch will become a no-op until re-enabled. Existing rules are preserved.',
        )) return;
        setTogglingAutomation(true);
        try {
            await notificationRuleService.setAutomation(next);
            const st = await notificationRuleService.automationStatus();
            setStatus(st);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not change automation state.');
        } finally {
            setTogglingAutomation(false);
        }
    };

    useEffect(() => { void refresh(); }, [refresh]);

    const handleCreate = async () => {
        if (!draft.slug.trim() || !draft.name.trim() || !draft.body_template.trim()) {
            alert('slug, name and body_template are required');
            return;
        }
        try {
            await notificationRuleService.create(draft);
            setShowCreate(false);
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not create rule.');
        }
    };

    const handleToggle = async (r: NotificationRule) => {
        try {
            await notificationRuleService.patch(r.id, { is_active: !r.is_active });
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not toggle.');
        }
    };

    const handleEvaluate = async (r: NotificationRule) => {
        setBusy(r.id);
        try {
            const s = await notificationRuleService.evaluate(r.id);
            alert(
                `Rule "${r.name}":\n` +
                `Queued ${s.queued}, ` +
                `skipped: consent=${s.skipped_consent}, ` +
                `cooldown=${s.skipped_cooldown}, ` +
                `frequency=${s.skipped_frequency}.` +
                (s.reasons?.length ? `\nReasons: ${s.reasons.join('; ')}` : ''),
            );
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Evaluate failed.');
        } finally {
            setBusy(null);
        }
    };

    const handleDispatchNow = async () => {
        if (!confirm(
            'Flush QUEUED deliveries now via IN_APP / EMAIL / WhatsApp?\n\n' +
            'Master flag notification_automation.enabled must be ON.',
        )) return;
        try {
            const s = await notificationRuleService.dispatchPending(200);
            alert(
                `Delivered ${s.delivered}, failed ${s.failed}` +
                (s.retried ? `, retrying ${s.retried}` : '') + '.',
            );
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Dispatch failed.');
        }
    };

    const openDeliveries = async (r: NotificationRule) => {
        setSelected(r);
        setDeliveries(null);
        try {
            const d = await notificationRuleService.deliveries(r.id, undefined, 100);
            setDeliveries(d);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not load deliveries.');
        }
    };

    return (
        <div className="max-w-6xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <Zap className="w-6 h-6 text-indigo-600" /> Notification automation
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Trigger-based rules. Fires every 30 min when{' '}
                        <code className="text-xs bg-gray-100 px-1 rounded">notification_automation.enabled</code>{' '}
                        is ON.
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={refresh}>
                        <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleDispatchNow}>
                        <Send className="w-4 h-4 mr-1" /> Dispatch pending
                    </Button>
                    <Button size="sm" onClick={() => setShowCreate(s => !s)}>
                        <Plus className="w-4 h-4 mr-1" /> New
                    </Button>
                </div>
            </div>

            {/* Automation settings + health dashboard */}
            {status && (
                <Card className={`p-5 mb-4 border ${status.enabled ? 'border-green-200 bg-green-50/40' : 'border-amber-200 bg-amber-50/40'}`}>
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="flex items-start gap-3">
                            <div className={`mt-0.5 rounded-lg p-2 ${status.enabled ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                                <Power className="w-5 h-5" />
                            </div>
                            <div>
                                <div className="flex items-center gap-2">
                                    <h2 className="font-semibold text-gray-900">Automation settings</h2>
                                    <Badge variant={status.enabled ? 'success' : 'warning'}>
                                        {status.enabled ? 'ENABLED' : 'DISABLED'}
                                    </Badge>
                                </div>
                                <p className="text-xs text-gray-600 mt-1 max-w-xl">
                                    Master switch <code className="text-[11px] bg-gray-100 px-1 rounded">notification_automation.enabled</code>.
                                    When ON, the scheduler evaluates active rules and dispatches queued
                                    notifications {status.scheduler.frequency}. Also editable from Tax&nbsp;Config.
                                </p>
                            </div>
                        </div>
                        <Button
                            size="sm"
                            variant={status.enabled ? 'outline' : 'primary'}
                            onClick={handleToggleAutomation}
                            isLoading={togglingAutomation}
                        >
                            <Power className="w-4 h-4 mr-1" />
                            {status.enabled ? 'Disable' : 'Enable'} automation
                        </Button>
                    </div>

                    {/* Health metrics */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-4">
                        <HealthStat
                            icon={<Activity className="w-4 h-4" />}
                            label="Scheduler"
                            value={status.scheduler.running ? 'Running' : 'Stopped'}
                            tone={status.scheduler.running ? 'good' : 'bad'}
                        />
                        <HealthStat
                            icon={<Clock className="w-4 h-4" />}
                            label="Next run"
                            value={status.scheduler.next_run_time
                                ? new Date(status.scheduler.next_run_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                                : '—'}
                            tone="neutral"
                        />
                        <HealthStat
                            icon={<Zap className="w-4 h-4" />}
                            label="Active rules"
                            value={`${status.rules.active}/${status.rules.total}`}
                            tone={status.rules.active > 0 ? 'good' : 'neutral'}
                        />
                        <HealthStat
                            icon={<Send className="w-4 h-4" />}
                            label="Queued"
                            value={String(status.deliveries.queued)}
                            tone={status.deliveries.queued > 0 ? 'warn' : 'neutral'}
                        />
                        <HealthStat
                            icon={<CheckCircle className="w-4 h-4" />}
                            label="Delivered today"
                            value={String(status.deliveries.delivered_today)}
                            tone="good"
                        />
                        <HealthStat
                            icon={<XCircle className="w-4 h-4" />}
                            label="Failed (total)"
                            value={String(status.deliveries.failed_total)}
                            tone={status.deliveries.failed_total > 0 ? 'bad' : 'neutral'}
                        />
                    </div>

                    <div className="flex flex-wrap gap-x-6 gap-y-1 mt-3 text-xs text-gray-500">
                        <span>
                            Last execution:{' '}
                            <span className="text-gray-700 font-medium">
                                {status.last_execution_time
                                    ? new Date(status.last_execution_time).toLocaleString()
                                    : 'never'}
                            </span>
                        </span>
                        <span>Dispatch batch size: <span className="text-gray-700 font-medium">{status.dispatch_batch_size}</span></span>
                        {!status.scheduler.job_registered && (
                            <span className="text-red-600 font-medium">⚠ Scheduler job not registered — backend may not have started the scheduler.</span>
                        )}
                    </div>

                    {status.last_error && (
                        <div className="mt-3 flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
                            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                            <span>
                                <span className="font-semibold">Last error</span> ({status.last_error.channel},{' '}
                                {new Date(status.last_error.at).toLocaleString()}): {status.last_error.reason || 'unknown'}
                            </span>
                        </div>
                    )}
                </Card>
            )}

            {showCreate && (
                <Card className="p-6 mb-4">
                    <h2 className="font-semibold text-gray-900 mb-3">New automation rule</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                            placeholder="slug"
                            className="border rounded px-3 py-2 text-sm"
                            value={draft.slug}
                            onChange={e => setDraft(d => ({ ...d, slug: e.target.value }))}
                        />
                        <input
                            placeholder="display name"
                            className="border rounded px-3 py-2 text-sm"
                            value={draft.name}
                            onChange={e => setDraft(d => ({ ...d, name: e.target.value }))}
                        />
                        <select
                            value={draft.trigger_type}
                            onChange={e => setDraft(d => ({ ...d, trigger_type: e.target.value as TriggerType }))}
                            className="border rounded px-3 py-2 text-sm"
                        >
                            {TRIGGERS.map(t => (
                                <option key={t} value={t}>{triggerLabel[t]}</option>
                            ))}
                        </select>
                        <select
                            value={draft.channel}
                            onChange={e => setDraft(d => ({ ...d, channel: e.target.value as CampaignChannel }))}
                            className="border rounded px-3 py-2 text-sm"
                        >
                            {CHANNELS.map(c => <option key={c}>{c}</option>)}
                        </select>
                        <input
                            type="number" placeholder="window (minutes)"
                            className="border rounded px-3 py-2 text-sm"
                            value={draft.trigger_window_minutes ?? 120}
                            onChange={e => setDraft(d => ({ ...d, trigger_window_minutes: parseInt(e.target.value || '0', 10) }))}
                        />
                        <input
                            type="number" placeholder="min events (for repeat-search)"
                            className="border rounded px-3 py-2 text-sm"
                            value={draft.min_event_count ?? 1}
                            onChange={e => setDraft(d => ({ ...d, min_event_count: parseInt(e.target.value || '0', 10) }))}
                        />
                        <input
                            type="number" placeholder="cooldown hours"
                            className="border rounded px-3 py-2 text-sm"
                            value={draft.cooldown_hours ?? 24}
                            onChange={e => setDraft(d => ({ ...d, cooldown_hours: parseInt(e.target.value || '0', 10) }))}
                        />
                        <input
                            type="number" placeholder="frequency cap"
                            className="border rounded px-3 py-2 text-sm"
                            value={draft.frequency_cap_per_user ?? 3}
                            onChange={e => setDraft(d => ({ ...d, frequency_cap_per_user: parseInt(e.target.value || '0', 10) }))}
                        />
                        <input
                            placeholder="subject (optional)"
                            className="border rounded px-3 py-2 text-sm md:col-span-2"
                            value={draft.subject_template ?? ''}
                            onChange={e => setDraft(d => ({ ...d, subject_template: e.target.value }))}
                        />
                        <textarea
                            placeholder="body template — use {{first_name}}"
                            rows={3}
                            className="border rounded px-3 py-2 text-sm md:col-span-2"
                            value={draft.body_template}
                            onChange={e => setDraft(d => ({ ...d, body_template: e.target.value }))}
                        />
                    </div>
                    <p className="text-xs text-gray-500 mt-2 flex items-start gap-1">
                        <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                        <span>Created inactive. Toggle ACTIVE only after testing.</span>
                    </p>
                    <div className="flex gap-2 mt-4">
                        <Button size="sm" onClick={handleCreate}>Create</Button>
                        <Button size="sm" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
                    </div>
                </Card>
            )}

            {error && (
                <Card className="p-4 mb-4 border-red-200 bg-red-50 text-red-700 text-sm">{error}</Card>
            )}

            {loading ? (
                <div className="text-gray-500">Loading…</div>
            ) : rules.length === 0 ? (
                <Card className="p-8 text-center text-gray-400">
                    No automation rules yet. Click "New" to create your first one.
                </Card>
            ) : (
                <Card className="p-0 overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rule</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Trigger</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Channel</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Throttle</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Active</th>
                                <th className="px-4 py-3" />
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {rules.map(r => (
                                <tr key={r.id} className="hover:bg-gray-50">
                                    <td className="px-4 py-3 text-sm">
                                        <div className="font-medium text-gray-900">{r.name}</div>
                                        <div className="text-xs text-gray-500 font-mono">{r.slug}</div>
                                    </td>
                                    <td className="px-4 py-3 text-xs text-gray-700">
                                        {triggerLabel[r.trigger_type]}
                                        <div className="text-gray-400">
                                            window {r.trigger_window_minutes}m
                                            {r.trigger_type === 'REPEAT_SEARCH_NO_BOOKING' && ` · ≥${r.min_event_count} events`}
                                        </div>
                                    </td>
                                    <td className="px-4 py-3 text-xs">
                                        <Badge variant="info" className="text-[10px]">{r.channel}</Badge>
                                    </td>
                                    <td className="px-4 py-3 text-xs text-gray-500">
                                        {r.cooldown_hours}h cooldown ·{' '}
                                        max {r.frequency_cap_per_user}/{r.frequency_cap_window_days}d
                                    </td>
                                    <td className="px-4 py-3">
                                        <button
                                            onClick={() => handleToggle(r)}
                                            className={`px-2 py-1 rounded text-xs ${r.is_active
                                                ? 'bg-green-100 text-green-700'
                                                : 'bg-gray-100 text-gray-500'}`}
                                        >
                                            {r.is_active ? 'ON' : 'OFF'}
                                        </button>
                                    </td>
                                    <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                                        <Button size="sm" variant="outline" onClick={() => openDeliveries(r)}>
                                            Deliveries
                                        </Button>
                                        <Button
                                            size="sm"
                                            onClick={() => handleEvaluate(r)}
                                            isLoading={busy === r.id}
                                            disabled={!r.is_active}
                                        >
                                            <Play className="w-3 h-3 mr-1" /> Evaluate
                                        </Button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {selected && (
                <Card className="p-6 mt-4">
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="font-semibold text-gray-900">
                            Recent deliveries: {selected.name}
                        </h2>
                        <button className="text-sm text-gray-500" onClick={() => setSelected(null)}>Close</button>
                    </div>
                    {deliveries === null ? (
                        <div className="text-gray-500 text-sm">Loading…</div>
                    ) : deliveries.length === 0 ? (
                        <div className="text-gray-400 text-sm">No deliveries yet.</div>
                    ) : (
                        <table className="min-w-full divide-y divide-gray-200 text-xs">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">User</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Status</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Queued</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Delivered</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Reason</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {deliveries.map(d => (
                                    <tr key={d.id}>
                                        <td className="px-3 py-2 font-mono text-gray-700">{d.user_id.slice(0, 12)}</td>
                                        <td className="px-3 py-2">
                                            <Badge variant={
                                                d.status === 'DELIVERED' ? 'success'
                                                    : d.status.startsWith('SKIPPED') ? 'warning'
                                                        : d.status === 'FAILED' ? 'error'
                                                            : 'info'
                                            }>{d.status}</Badge>
                                        </td>
                                        <td className="px-3 py-2 text-gray-500">
                                            {new Date(d.queued_at).toLocaleString()}
                                        </td>
                                        <td className="px-3 py-2 text-gray-500">
                                            {d.delivered_at ? new Date(d.delivered_at).toLocaleString() : '—'}
                                        </td>
                                        <td className="px-3 py-2 text-gray-500 max-w-xs truncate" title={d.reason || ''}>
                                            {d.reason || '—'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </Card>
            )}
        </div>
    );
};

export default SuperAdminNotificationRules;
