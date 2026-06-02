/**
 * Super-admin campaigns page (Phase 4B).
 *
 * Lists campaigns. New-campaign form requires a target segment id (paste in
 * for now — segment picker can be a Phase 5 polish). Enqueue button creates
 * QUEUED deliveries (Phase 4C will actually send them). Funnel view shows
 * the audit funnel including skipped-with-reason counts.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { FeatureFlagToggle } from '../components/FeatureFlagToggle';
import {
    ArrowLeft, Play, RefreshCw, Plus, BarChart3, AlertCircle, Send,
} from 'lucide-react';
import {
    campaignService, Campaign, CampaignChannel, CampaignInput, CampaignStatus,
    Delivery, Funnel,
} from '../services/campaignService';
import { segmentService, Segment } from '../services/segmentService';

const CHANNELS: CampaignChannel[] = ['IN_APP', 'EMAIL', 'PUSH', 'WHATSAPP'];
const STATUSES: CampaignStatus[] = ['DRAFT', 'ACTIVE', 'PAUSED', 'COMPLETED'];

const statusVariant = (s: CampaignStatus): 'success' | 'warning' | 'info' | 'error' => {
    switch (s) {
        case 'ACTIVE': return 'success';
        case 'DRAFT': return 'info';
        case 'PAUSED': return 'warning';
        case 'COMPLETED': return 'info';
    }
};

export const SuperAdminCampaigns: React.FC = () => {
    const navigate = useNavigate();
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);
    const [segments, setSegments] = useState<Segment[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState<string | null>(null);

    const [showCreate, setShowCreate] = useState(false);
    const [draft, setDraft] = useState<CampaignInput>({
        slug: '', name: '', body_template: '',
        segment_id: '', channel: 'IN_APP',
        cooldown_hours: 24, frequency_cap_per_user: 3, frequency_cap_window_days: 7,
    });

    const [selected, setSelected] = useState<Campaign | null>(null);
    const [funnel, setFunnel] = useState<Funnel | null>(null);
    const [deliveries, setDeliveries] = useState<Delivery[] | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [cs, ss] = await Promise.all([
                campaignService.list(true),
                segmentService.list(true).catch(() => []),
            ]);
            setCampaigns(cs);
            setSegments(ss);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load campaigns.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void refresh(); }, [refresh]);

    const handleCreate = async () => {
        if (!draft.slug.trim() || !draft.name.trim() || !draft.body_template.trim()) {
            alert('slug, name and body_template are required');
            return;
        }
        if (!draft.segment_id.trim()) {
            alert('segment_id is required — pick from the dropdown');
            return;
        }
        try {
            await campaignService.create(draft);
            setShowCreate(false);
            setDraft({
                slug: '', name: '', body_template: '',
                segment_id: '', channel: 'IN_APP',
                cooldown_hours: 24, frequency_cap_per_user: 3, frequency_cap_window_days: 7,
            });
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not create campaign.');
        }
    };

    const handleStatusChange = async (c: Campaign, status: CampaignStatus) => {
        try {
            await campaignService.patch(c.id, { status });
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not update status.');
        }
    };

    const handleEnqueue = async (c: Campaign) => {
        if (!confirm(
            `Enqueue eligible deliveries for "${c.name}"?\n\n` +
            `Campaign must be ACTIVE and campaigns.enabled must be ON. ` +
            `Phase 4B only queues — sending lands in Phase 4C.`,
        )) return;
        setBusy(c.id);
        try {
            const s = await campaignService.enqueue(c.id);
            alert(
                `Queued ${s.queued}, ` +
                `skipped: consent=${s.skipped_consent}, cooldown=${s.skipped_cooldown}, frequency=${s.skipped_frequency}.` +
                (s.reasons?.length ? `\nReasons: ${s.reasons.join('; ')}` : ''),
            );
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Enqueue failed.');
        } finally {
            setBusy(null);
        }
    };

    const openFunnel = async (c: Campaign) => {
        setSelected(c);
        setFunnel(null);
        setDeliveries(null);
        try {
            const [f, d] = await Promise.all([
                campaignService.funnel(c.id),
                campaignService.deliveries(c.id, undefined, 100),
            ]);
            setFunnel(f);
            setDeliveries(d);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not load funnel.');
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
            <FeatureFlagToggle
                flagKey="campaigns.enabled"
                label="Campaign delivery"
                description="Dispatch drafted campaigns to their target segments"
                onChange={() => void refresh()}
            />
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <Send className="w-6 h-6 text-indigo-600" /> Campaigns
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Targeted outreach by segment. Phase 4B: queue + attribute.
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={refresh}>
                        <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                    </Button>
                    <Button size="sm" onClick={() => setShowCreate(s => !s)}>
                        <Plus className="w-4 h-4 mr-1" /> New
                    </Button>
                </div>
            </div>

            {showCreate && (
                <Card className="p-6 mb-4">
                    <h2 className="font-semibold text-gray-900 mb-3">New campaign</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                            placeholder="slug (e.g. kochi-cabin-3000)"
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
                            value={draft.segment_id}
                            onChange={e => setDraft(d => ({ ...d, segment_id: e.target.value }))}
                            className="border rounded px-3 py-2 text-sm md:col-span-2"
                        >
                            <option value="">— select target segment —</option>
                            {segments.map(s => (
                                <option key={s.id} value={s.id}>{s.name} ({s.slug})</option>
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
                            type="number" placeholder="cooldown hours"
                            className="border rounded px-3 py-2 text-sm"
                            value={draft.cooldown_hours ?? 24}
                            onChange={e => setDraft(d => ({ ...d, cooldown_hours: parseInt(e.target.value || '0', 10) }))}
                        />
                        <input
                            type="number" placeholder="frequency cap (deliveries/user)"
                            className="border rounded px-3 py-2 text-sm"
                            value={draft.frequency_cap_per_user ?? 3}
                            onChange={e => setDraft(d => ({ ...d, frequency_cap_per_user: parseInt(e.target.value || '0', 10) }))}
                        />
                        <input
                            type="number" placeholder="frequency cap window (days)"
                            className="border rounded px-3 py-2 text-sm"
                            value={draft.frequency_cap_window_days ?? 7}
                            onChange={e => setDraft(d => ({ ...d, frequency_cap_window_days: parseInt(e.target.value || '0', 10) }))}
                        />
                        <textarea
                            placeholder="body template"
                            rows={3}
                            className="border rounded px-3 py-2 text-sm md:col-span-2"
                            value={draft.body_template}
                            onChange={e => setDraft(d => ({ ...d, body_template: e.target.value }))}
                        />
                    </div>
                    <p className="text-xs text-gray-500 mt-2 flex items-start gap-1">
                        <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                        <span>New campaigns start in DRAFT. Flip to ACTIVE before enqueueing.</span>
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
            ) : campaigns.length === 0 ? (
                <Card className="p-8 text-center text-gray-400">
                    No campaigns yet. Click "New" to create your first one.
                </Card>
            ) : (
                <Card className="p-0 overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Campaign</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Channel</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cooldown / Cap</th>
                                <th className="px-4 py-3" />
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {campaigns.map(c => (
                                <tr key={c.id} className="hover:bg-gray-50">
                                    <td className="px-4 py-3 text-sm">
                                        <div className="font-medium text-gray-900">{c.name}</div>
                                        <div className="text-xs text-gray-500 font-mono">{c.slug}</div>
                                    </td>
                                    <td className="px-4 py-3 text-xs">
                                        <Badge variant="info" className="text-[10px]">{c.channel}</Badge>
                                    </td>
                                    <td className="px-4 py-3">
                                        <select
                                            className="border rounded px-2 py-1 text-xs"
                                            value={c.status}
                                            onChange={e => handleStatusChange(c, e.target.value as CampaignStatus)}
                                        >
                                            {STATUSES.map(s => <option key={s}>{s}</option>)}
                                        </select>
                                    </td>
                                    <td className="px-4 py-3 text-xs text-gray-500">
                                        {c.cooldown_hours}h cooldown ·{' '}
                                        max {c.frequency_cap_per_user}/{c.frequency_cap_window_days}d
                                    </td>
                                    <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                                        <Button size="sm" variant="outline" onClick={() => openFunnel(c)}>
                                            <BarChart3 className="w-3 h-3 mr-1" /> Funnel
                                        </Button>
                                        <Button
                                            size="sm"
                                            onClick={() => handleEnqueue(c)}
                                            isLoading={busy === c.id}
                                            disabled={c.status !== 'ACTIVE'}
                                        >
                                            <Play className="w-3 h-3 mr-1" /> Enqueue
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
                            Funnel: {selected.name}
                        </h2>
                        <button className="text-sm text-gray-500" onClick={() => setSelected(null)}>Close</button>
                    </div>
                    {funnel === null ? (
                        <div className="text-gray-500 text-sm">Loading…</div>
                    ) : (
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4 text-sm">
                            <div><span className="text-gray-500">Queued/Delivered:</span> <b>{funnel.delivered}</b> of {funnel.queued}</div>
                            <div><span className="text-gray-500">Opened:</span> <b>{funnel.opened}</b></div>
                            <div><span className="text-gray-500">Clicked:</span> <b>{funnel.clicked}</b></div>
                            <div><span className="text-gray-500">Converted:</span> <b>{funnel.converted}</b></div>
                            <div className="text-xs text-gray-400">
                                Skipped: consent {funnel.skipped_consent} ·
                                cooldown {funnel.skipped_cooldown} ·
                                freq {funnel.skipped_frequency}
                                {funnel.failed > 0 && ` · failed ${funnel.failed}`}
                            </div>
                        </div>
                    )}

                    {deliveries !== null && deliveries.length > 0 && (
                        <table className="min-w-full divide-y divide-gray-200 text-xs">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">User</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Status</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Opened</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Clicked</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Converted</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Reason</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {deliveries.map(d => (
                                    <tr key={d.id}>
                                        <td className="px-3 py-2 font-mono text-gray-700">{d.user_id.slice(0, 12)}</td>
                                        <td className="px-3 py-2"><Badge variant={
                                            d.status === 'DELIVERED' ? 'success'
                                                : d.status.startsWith('SKIPPED') ? 'warning'
                                                : d.status === 'FAILED' ? 'error'
                                                : 'info'
                                        }>{d.status}</Badge></td>
                                        <td className="px-3 py-2 text-gray-500">{d.opened_at ? '✓' : '—'}</td>
                                        <td className="px-3 py-2 text-gray-500">{d.clicked_at ? '✓' : '—'}</td>
                                        <td className="px-3 py-2 text-gray-500 font-mono">
                                            {d.converted_booking_id ? d.converted_booking_id.slice(0, 8) : '—'}
                                        </td>
                                        <td className="px-3 py-2 text-gray-500">{d.reason || '—'}</td>
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

export default SuperAdminCampaigns;
