/**
 * Super-admin segments page (Phase 4A).
 *
 * Lists active segments, lets super-admin recompute, create new ones with
 * a small built-in builder for each rule_type, and drill into member lists.
 *
 * Campaign builder + notification automation land in Phase 4B/C and will
 * read the segments this page creates.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { FeatureFlagToggle } from '../components/FeatureFlagToggle';
import {
    ArrowLeft, Play, RefreshCw, Plus, Trash2, Users, AlertCircle,
} from 'lucide-react';
import {
    segmentService, Segment, SegmentRuleType, SegmentInput, SegmentMember,
} from '../services/segmentService';

const RULE_TYPES: SegmentRuleType[] = [
    'HIGH_INTENT', 'BUDGET_BAND', 'CITY_INTEREST', 'AMENITY_INTEREST',
    'PAYMENT_ABANDONED', 'REPEAT_SEARCH_NO_BOOKING', 'CANCELLED_USERS',
];

const ruleHint: Record<SegmentRuleType, string> = {
    HIGH_INTENT: 'No config needed. Matches users with intent HIGH or HOT.',
    BUDGET_BAND: 'rule_config: {"max_price": 3000}',
    CITY_INTEREST: 'rule_config: {"city": "Kochi"}',
    AMENITY_INTEREST: 'rule_config: {"amenity": "AC"}',
    PAYMENT_ABANDONED: 'No config needed. Matches users with payment.failed event in window.',
    REPEAT_SEARCH_NO_BOOKING: 'rule_config: {"min_searches": 3}',
    CANCELLED_USERS: 'No config needed. Matches users with CANCELLATION event in window.',
};

export const SuperAdminSegments: React.FC = () => {
    const navigate = useNavigate();
    const [segments, setSegments] = useState<Segment[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    // Drill-down
    const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null);
    const [members, setMembers] = useState<SegmentMember[] | null>(null);

    // Create form
    const [showCreate, setShowCreate] = useState(false);
    const [draft, setDraft] = useState<SegmentInput>({
        slug: '', name: '', rule_type: 'HIGH_INTENT', rule_config: {},
    });
    const [draftConfigText, setDraftConfigText] = useState('{}');

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const list = await segmentService.list(true);
            setSegments(list);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load segments.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void refresh(); }, [refresh]);

    const handleRecompute = async () => {
        if (!confirm(
            'Recompute every active segment now? Honors segments.enabled — if OFF, nothing happens.',
        )) return;
        setBusy(true);
        try {
            const summary = await segmentService.recompute();
            alert(
                `Evaluated ${summary.segments_evaluated} segments. ` +
                `Entered ${summary.memberships_entered}, exited ${summary.memberships_exited}.` +
                (summary.skipped?.length ? `\nSkipped: ${summary.skipped.join(', ')}` : ''),
            );
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Recompute failed.');
        } finally {
            setBusy(false);
        }
    };

    const handleCreate = async () => {
        let config: Record<string, unknown>;
        try {
            const parsed = JSON.parse(draftConfigText);
            if (typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('not an object');
            config = parsed as Record<string, unknown>;
        } catch {
            alert('rule_config must be a JSON object.');
            return;
        }
        if (!draft.slug.trim() || !draft.name.trim()) {
            alert('Slug and name are required.');
            return;
        }
        setBusy(true);
        try {
            await segmentService.create({ ...draft, rule_config: config });
            setShowCreate(false);
            setDraft({ slug: '', name: '', rule_type: 'HIGH_INTENT', rule_config: {} });
            setDraftConfigText('{}');
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not create segment.');
        } finally {
            setBusy(false);
        }
    };

    const handleSoftDelete = async (segment: Segment) => {
        if (!confirm(`Disable segment "${segment.name}"? History will be preserved.`)) return;
        try {
            await segmentService.softDelete(segment.id);
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not disable.');
        }
    };

    const openMembers = async (segment: Segment) => {
        setSelectedSegment(segment);
        setMembers(null);
        try {
            const ms = await segmentService.members(segment.id);
            setMembers(ms);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not load members.');
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
                flagKey="segments.enabled"
                label="Audience segments"
                description="Nightly recomputation of segments from event history"
                onChange={() => void refresh()}
            />
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <Users className="w-6 h-6 text-indigo-600" /> User Segments
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Rule-based audience segments. Memberships refresh nightly.
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={refresh}>
                        <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                    </Button>
                    <Button size="sm" onClick={handleRecompute} isLoading={busy}>
                        <Play className="w-4 h-4 mr-1" /> Recompute Now
                    </Button>
                    <Button size="sm" onClick={() => setShowCreate(s => !s)}>
                        <Plus className="w-4 h-4 mr-1" /> New
                    </Button>
                </div>
            </div>

            {showCreate && (
                <Card className="p-6 mb-4">
                    <h2 className="font-semibold text-gray-900 mb-3">New segment</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                            placeholder="slug (e.g. high-intent-kochi)"
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
                            value={draft.rule_type}
                            onChange={e => {
                                const v = e.target.value as SegmentRuleType;
                                setDraft(d => ({ ...d, rule_type: v }));
                            }}
                            className="border rounded px-3 py-2 text-sm md:col-span-2"
                        >
                            {RULE_TYPES.map(rt => <option key={rt}>{rt}</option>)}
                        </select>
                        <textarea
                            placeholder="rule_config (JSON object)"
                            className="border rounded px-3 py-2 text-sm md:col-span-2 font-mono"
                            rows={3}
                            value={draftConfigText}
                            onChange={e => setDraftConfigText(e.target.value)}
                        />
                        <p className="text-xs text-gray-500 md:col-span-2 flex items-start gap-1">
                            <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                            <span>{ruleHint[draft.rule_type]}</span>
                        </p>
                    </div>
                    <div className="flex gap-2 mt-4">
                        <Button size="sm" onClick={handleCreate} isLoading={busy}>Create</Button>
                        <Button size="sm" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
                    </div>
                </Card>
            )}

            {error && (
                <Card className="p-4 mb-4 border-red-200 bg-red-50 text-red-700 text-sm">{error}</Card>
            )}

            {loading ? (
                <div className="text-gray-500">Loading…</div>
            ) : segments.length === 0 ? (
                <Card className="p-8 text-center text-gray-400">
                    No segments yet. Click "New" to create your first one.
                </Card>
            ) : (
                <Card className="p-0 overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Segment</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rule</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Updated</th>
                                <th className="px-4 py-3" />
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {segments.map(s => (
                                <tr key={s.id} className="hover:bg-gray-50">
                                    <td className="px-4 py-3 text-sm">
                                        <div className="font-medium text-gray-900">{s.name}</div>
                                        <div className="text-xs text-gray-500 font-mono">{s.slug}</div>
                                    </td>
                                    <td className="px-4 py-3 text-xs">
                                        <Badge variant="info" className="text-[10px]">{s.rule_type}</Badge>
                                        {Object.keys(s.rule_config).length > 0 && (
                                            <code className="block text-gray-500 mt-1 font-mono">
                                                {JSON.stringify(s.rule_config)}
                                            </code>
                                        )}
                                    </td>
                                    <td className="px-4 py-3">
                                        <Badge variant={s.is_active ? 'success' : 'warning'} className="text-xs">
                                            {s.is_active ? 'active' : 'disabled'}
                                        </Badge>
                                    </td>
                                    <td className="px-4 py-3 text-xs text-gray-500">
                                        {new Date(s.updated_at).toLocaleString('en-IN')}
                                    </td>
                                    <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                                        <Button size="sm" variant="outline" onClick={() => openMembers(s)}>
                                            <Users className="w-3 h-3 mr-1" /> Members
                                        </Button>
                                        {s.is_active && (
                                            <Button size="sm" variant="outline" onClick={() => handleSoftDelete(s)}>
                                                <Trash2 className="w-3 h-3 mr-1" /> Disable
                                            </Button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {selectedSegment && (
                <Card className="p-6 mt-4">
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="font-semibold text-gray-900">
                            Members of "{selectedSegment.name}"
                        </h2>
                        <button className="text-sm text-gray-500" onClick={() => setSelectedSegment(null)}>Close</button>
                    </div>
                    {members === null ? (
                        <div className="text-gray-500 text-sm">Loading…</div>
                    ) : members.length === 0 ? (
                        <div className="text-gray-400 text-sm">No active members.</div>
                    ) : (
                        <table className="min-w-full divide-y divide-gray-200 text-sm">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase text-xs">User</th>
                                    <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase text-xs">Score</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase text-xs">Reason</th>
                                    <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase text-xs">Entered</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {members.map(m => (
                                    <tr key={m.user_id}>
                                        <td className="px-3 py-2 font-mono text-gray-700">{m.user_id.slice(0, 12)}</td>
                                        <td className="px-3 py-2 text-right text-gray-900">{m.score.toFixed(2)}</td>
                                        <td className="px-3 py-2 text-gray-500">{m.reason || '—'}</td>
                                        <td className="px-3 py-2 text-gray-500">
                                            {new Date(m.entered_at).toLocaleString('en-IN')}
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

export default SuperAdminSegments;
