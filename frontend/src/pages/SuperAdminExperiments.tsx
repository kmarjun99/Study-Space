/**
 * Super-admin A/B experiments page (Phase 6).
 *
 * Lists experiments, create form, results drawer with per-variant
 * conversion rate + significance flag (z-score-based).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ArrowLeft, RefreshCw, Plus, Beaker, AlertCircle, BarChart3, Download,
} from 'lucide-react';
import { Card, Button, Badge } from '../components/UI';
import { FeatureFlagToggle } from '../components/FeatureFlagToggle';
import {
    experimentService, Experiment, ExperimentInput, ExperimentResults,
    ExperimentStatus,
} from '../services/experimentService';

const STATUSES: ExperimentStatus[] = ['DRAFT', 'RUNNING', 'PAUSED', 'COMPLETED'];

const fmtPct = (x: number): string => `${(x * 100).toFixed(2)}%`;

const statusVariant = (s: ExperimentStatus): 'success' | 'warning' | 'info' => {
    switch (s) {
        case 'RUNNING': return 'success';
        case 'PAUSED': return 'warning';
        default: return 'info';
    }
};

export const SuperAdminExperiments: React.FC = () => {
    const navigate = useNavigate();
    const [list, setList] = useState<Experiment[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [showCreate, setShowCreate] = useState(false);
    const [draft, setDraft] = useState<ExperimentInput>({
        slug: '', name: '',
        hypothesis: 'Treatment improves conversion.',
        variants: [
            { name: 'control', weight: 50 },
            { name: 'treatment', weight: 50 },
        ],
        success_event_name: 'booking.completed',
    });

    const [selected, setSelected] = useState<Experiment | null>(null);
    const [results, setResults] = useState<ExperimentResults | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            setList(await experimentService.list());
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load experiments.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void refresh(); }, [refresh]);

    const handleCreate = async () => {
        if (!draft.slug.trim() || !draft.name.trim()) {
            alert('slug and name are required');
            return;
        }
        try {
            await experimentService.create(draft);
            setShowCreate(false);
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not create experiment.');
        }
    };

    const handleStatusChange = async (exp: Experiment, status: ExperimentStatus) => {
        try {
            await experimentService.patch(exp.id, { status });
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not update.');
        }
    };

    const openResults = async (exp: Experiment) => {
        setSelected(exp);
        setResults(null);
        try {
            setResults(await experimentService.results(exp.slug));
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not load results.');
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
                flagKey="experiments.enabled"
                label="Experiments (A/B)"
                description="A/B testing framework — variant assignment & results"
                onChange={() => void refresh()}
            />
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <Beaker className="w-6 h-6 text-indigo-600" /> A/B experiments
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Deterministic variant assignment + frequentist z-test.
                    </p>
                </div>
                <div className="flex gap-2">
                    <a
                        href={`/api${experimentService.featureCsvUrl(30)}`}
                        className="inline-flex items-center text-sm border border-gray-300 rounded px-3 py-1 hover:bg-gray-50"
                    >
                        <Download className="w-4 h-4 mr-1" /> features.csv
                    </a>
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
                    <h2 className="font-semibold text-gray-900 mb-3">New experiment</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                            placeholder="slug (lowercase-kebab)"
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
                        <input
                            placeholder="success_event_name (e.g. booking.completed)"
                            className="border rounded px-3 py-2 text-sm md:col-span-2"
                            value={draft.success_event_name ?? ''}
                            onChange={e => setDraft(d => ({ ...d, success_event_name: e.target.value }))}
                        />
                        <textarea
                            placeholder="hypothesis"
                            rows={2}
                            className="border rounded px-3 py-2 text-sm md:col-span-2"
                            value={draft.hypothesis ?? ''}
                            onChange={e => setDraft(d => ({ ...d, hypothesis: e.target.value }))}
                        />
                        {draft.variants.map((v, i) => (
                            <div key={i} className="flex gap-2 items-center">
                                <input
                                    placeholder="variant name"
                                    className="border rounded px-3 py-2 text-sm flex-1"
                                    value={v.name}
                                    onChange={e => {
                                        const variants = [...draft.variants];
                                        variants[i] = { ...variants[i], name: e.target.value };
                                        setDraft(d => ({ ...d, variants }));
                                    }}
                                />
                                <input
                                    type="number" placeholder="weight"
                                    className="border rounded px-3 py-2 text-sm w-24"
                                    value={v.weight}
                                    onChange={e => {
                                        const variants = [...draft.variants];
                                        variants[i] = { ...variants[i], weight: parseInt(e.target.value || '0', 10) };
                                        setDraft(d => ({ ...d, variants }));
                                    }}
                                />
                            </div>
                        ))}
                    </div>
                    <p className="text-xs text-gray-500 mt-2 flex items-start gap-1">
                        <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                        <span>First variant is treated as control for significance testing. Created DRAFT — flip to RUNNING to start bucketing.</span>
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
            ) : list.length === 0 ? (
                <Card className="p-8 text-center text-gray-400">
                    No experiments yet. Click "New" to create one.
                </Card>
            ) : (
                <Card className="p-0 overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Experiment</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Variants</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Success event</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th className="px-4 py-3" />
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {list.map(exp => (
                                <tr key={exp.id} className="hover:bg-gray-50">
                                    <td className="px-4 py-3 text-sm">
                                        <div className="font-medium text-gray-900">{exp.name}</div>
                                        <div className="text-xs text-gray-500 font-mono">{exp.slug}</div>
                                    </td>
                                    <td className="px-4 py-3 text-xs text-gray-700">
                                        {exp.variants.map(v => `${v.name}:${v.weight}`).join(' · ')}
                                    </td>
                                    <td className="px-4 py-3 text-xs font-mono text-gray-500">{exp.success_event_name}</td>
                                    <td className="px-4 py-3">
                                        <select
                                            className="border rounded px-2 py-1 text-xs"
                                            value={exp.status}
                                            onChange={e => handleStatusChange(exp, e.target.value as ExperimentStatus)}
                                        >
                                            {STATUSES.map(s => <option key={s}>{s}</option>)}
                                        </select>
                                        <Badge variant={statusVariant(exp.status)} className="ml-2 text-[10px]">{exp.status}</Badge>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <Button size="sm" variant="outline" onClick={() => openResults(exp)}>
                                            <BarChart3 className="w-3 h-3 mr-1" /> Results
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
                            Results: {selected.name}
                        </h2>
                        <button className="text-sm text-gray-500" onClick={() => setSelected(null)}>Close</button>
                    </div>
                    {results === null ? (
                        <div className="text-gray-500 text-sm">Loading…</div>
                    ) : (
                        <table className="min-w-full divide-y divide-gray-200 text-sm">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Variant</th>
                                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Exposures</th>
                                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Converters</th>
                                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">CR</th>
                                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Lift vs control</th>
                                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">z</th>
                                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">95% sig.</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {results.variants.map(v => {
                                    const sig = results.significance?.[v.variant];
                                    const isCtrl = v.variant === results.control_variant;
                                    return (
                                        <tr key={v.variant}>
                                            <td className="px-3 py-2 font-medium text-gray-900">
                                                {v.variant} {isCtrl && <span className="text-xs text-gray-400">(control)</span>}
                                            </td>
                                            <td className="px-3 py-2 text-right">{v.exposures.toLocaleString()}</td>
                                            <td className="px-3 py-2 text-right">{v.converters.toLocaleString()}</td>
                                            <td className="px-3 py-2 text-right">{fmtPct(v.conversion_rate)}</td>
                                            <td className="px-3 py-2 text-right text-gray-500">
                                                {sig ? `${sig.lift >= 0 ? '+' : ''}${fmtPct(sig.lift)}` : '—'}
                                            </td>
                                            <td className="px-3 py-2 text-right text-gray-500">
                                                {sig?.z !== null && sig?.z !== undefined ? sig.z.toFixed(3) : '—'}
                                            </td>
                                            <td className="px-3 py-2 text-right">
                                                {isCtrl ? '—'
                                                    : sig?.is_significant_at_95
                                                        ? <Badge variant="success" className="text-[10px]">YES</Badge>
                                                        : <Badge variant="warning" className="text-[10px]">no</Badge>}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </Card>
            )}
        </div>
    );
};

export default SuperAdminExperiments;
