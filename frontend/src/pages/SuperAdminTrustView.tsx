
import React, { useState, useEffect } from 'react';
import { Card, Button, Badge } from '../components/UI';
import { Building2, Users, Flag, CheckCircle, AlertTriangle } from 'lucide-react';
import { User } from '../types';
import { trustService } from '../services/trustService';
import { supplyService } from '../services/supplyService';

interface SuperAdminTrustViewProps {
    users: User[];
    currentUser: User | null;
}

export const SuperAdminTrustView: React.FC<SuperAdminTrustViewProps> = ({ users, currentUser }) => {
    const [venues, setVenues] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'overview' | 'flags' | 'reminders' | 'audit'>('overview');

    // Trust data states
    const [flags, setFlags] = useState<any[]>([]);
    const [reminders, setReminders] = useState<any[]>([]);
    const [auditLog, setAuditLog] = useState<any[]>([]);
    const [auditTotal, setAuditTotal] = useState(0);

    // Action states
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [selectedFlag, setSelectedFlag] = useState<any | null>(null);
    const [resolveModalOpen, setResolveModalOpen] = useState(false);
    const [resolveNotes, setResolveNotes] = useState('');

    // Flag Creation State
    const [flagModalOpen, setFlagModalOpen] = useState(false);
    const [selectedVenue, setSelectedVenue] = useState<any | null>(null);
    const [flagReason, setFlagReason] = useState('');

    // Audit filters
    const [auditActionFilter, setAuditActionFilter] = useState('');
    const [auditEntityFilter, setAuditEntityFilter] = useState('');

    useEffect(() => {
        loadAllData();
    }, []);

    const loadAllData = async () => {
        setLoading(true);
        try {
            // Load venues for compliance check
            const v = await supplyService.getAllReadingRooms();
            setVenues(v);

            const [flagsData, remindersData, auditData] = await Promise.all([
                trustService.getAllFlags().catch(() => []),
                trustService.getAllReminders().catch(() => []),
                trustService.getAuditLog({ limit: 50 }).catch(() => ({ entries: [], total: 0 }))
            ]);

            setFlags(flagsData);
            setReminders(remindersData);
            setAuditLog(auditData.entries || []);
            setAuditTotal(auditData.total || 0);
        } catch (err) {
            console.error("Trust data load failed", err);
        } finally {
            setLoading(false);
        }
    };

    // --- Compliance Analysis ---
    const flaggedVenues = venues.filter(v => {
        const hasPhone = !!v.contactPhone;
        const hasImage = !!v.imageUrl;
        const hasDesc = v.description && v.description.length > 5;
        return !hasPhone || !hasImage || !hasDesc;
    });

    const unverifiedUsers = users.filter(u => !u.phone);

    // Scores
    const venueComplianceScore = Math.round(((venues.length - flaggedVenues.length) / (venues.length || 1)) * 100);
    const userVerificationRate = Math.round(((users.length - unverifiedUsers.length) / (users.length || 1)) * 100);

    // --- Action Handlers ---
    const handleFlagVenueClick = (venue: any) => {
        setSelectedVenue(venue);
        setFlagReason(''); // Reset reason
        setFlagModalOpen(true);
    };

    const confirmFlagVenue = async () => {
        if (!selectedVenue) return;

        // Validation: Require reason
        if (!flagReason.trim()) {
            alert("Please provide a reason for flagging and non-compliance.");
            return;
        }

        setActionLoading(selectedVenue.id);
        try {
            // Determine flag type based on issues
            let flagType = 'other';
            if (!selectedVenue.contactPhone) flagType = 'missing_phone';
            else if (!selectedVenue.imageUrl) flagType = 'missing_images';
            else if (!selectedVenue.description || selectedVenue.description.length <= 5) flagType = 'weak_description';

            await trustService.createFlag(
                'reading_room',
                selectedVenue.id,
                flagType as any,
                flagReason, // Use the custom reason input
                currentUser?.id,
                currentUser?.name
            );

            alert(`✅ Flag created for "${selectedVenue.name}". Owner will see: "${flagReason}"`);
            setFlagModalOpen(false);
            setSelectedVenue(null);
            loadAllData();
        } catch (err: any) {
            console.error("Flag creation failed", err);
            alert(`❌ Failed to create flag: ${err.response?.data?.detail || err.message}`);
        } finally {
            setActionLoading(null);
        }
    };

    const handleRemindUser = async (user: any) => {
        if (!confirm(`Send verification reminder to "${user.name}"?`)) return;

        setActionLoading(user.id);
        try {
            await trustService.sendReminder(
                user.id,
                'phone',
                ['phone'],
                'Please complete your phone verification to continue using the platform.',
                true, // blocks listings
                true, // blocks payments
                false, // blocks bookings
                currentUser?.id,
                currentUser?.name
            );

            alert(`✅ Reminder sent to "${user.name}". User will see verification block.`);
            loadAllData();
        } catch (err: any) {
            console.error("Reminder send failed", err);
            alert(`❌ Failed to send reminder: ${err.response?.data?.detail || err.message}`);
        } finally {
            setActionLoading(null);
        }
    };

    const handleResolveFlag = async (action: 'approve' | 'reject' | 'escalate') => {
        if (!selectedFlag) return;

        setActionLoading(selectedFlag.id);
        try {
            await trustService.resolveFlag(
                selectedFlag.id,
                action,
                resolveNotes,
                currentUser?.id,
                currentUser?.name
            );

            const actionText = action === 'approve' ? 'resolved' : action === 'reject' ? 'rejected' : 'escalated';
            alert(`✅ Flag ${actionText} successfully.`);
            setResolveModalOpen(false);
            setSelectedFlag(null);
            setResolveNotes('');
            loadAllData();
        } catch (err: any) {
            console.error("Flag resolution failed", err);
            alert(`❌ Failed to resolve flag: ${err.response?.data?.detail || err.message}`);
        } finally {
            setActionLoading(null);
        }
    };

    const loadAuditLog = async () => {
        try {
            const data = await trustService.getAuditLog({
                actionType: auditActionFilter || undefined,
                entityType: auditEntityFilter || undefined,
                limit: 100
            });
            setAuditLog(data.entries || []);
            setAuditTotal(data.total || 0);
        } catch (err) {
            console.error("Audit log load failed", err);
        }
    };

    useEffect(() => {
        if (activeTab === 'audit') {
            loadAuditLog();
        }
    }, [activeTab, auditActionFilter, auditEntityFilter]);

    // Count active issues
    const activeFlags = flags.filter(f => f.status === 'active' || f.status === 'owner_resubmitted');
    const pendingReminders = reminders.filter(r => r.status === 'pending');

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Trust & Safety</h2>
                    <p className="text-gray-500">Platform compliance, risk monitoring, and moderation.</p>
                </div>
                <div className="flex gap-2">
                    {['overview', 'flags', 'reminders', 'audit'].map(tab => (
                        <Button
                            key={tab}
                            variant={activeTab === tab ? 'primary' : 'outline'}
                            onClick={() => setActiveTab(tab as any)}
                        >
                            {tab === 'overview' && 'Overview'}
                            {tab === 'flags' && `Flags (${activeFlags.length})`}
                            {tab === 'reminders' && `Reminders (${pendingReminders.length})`}
                            {tab === 'audit' && 'Audit Log'}
                        </Button>
                    ))}
                </div>
            </div>

            {activeTab === 'overview' && (
                <>
                    {/* Safety Pulse */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <Card className="p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-gray-700">Compliance Score</h3>
                                {venueComplianceScore > 80 ? <CheckCircle className="text-green-500 w-6 h-6" /> : <AlertTriangle className="text-orange-500 w-6 h-6" />}
                            </div>
                            <div className="flex items-end gap-2">
                                <span className="text-4xl font-extrabold text-gray-900">{venueComplianceScore}%</span>
                                <span className="text-sm text-gray-500 mb-1">of venues meet standards</span>
                            </div>
                            <div className="w-full bg-gray-100 rounded-full h-2 mt-4">
                                <div className={`h-2 rounded-full ${venueComplianceScore > 80 ? 'bg-green-500' : 'bg-orange-500'}`} style={{ width: `${venueComplianceScore}%` }}></div>
                            </div>
                        </Card>

                        <Card className="p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-gray-700">Identity Health</h3>
                                <Users className="text-indigo-500 w-6 h-6" />
                            </div>
                            <div className="flex items-end gap-2">
                                <span className="text-4xl font-extrabold text-gray-900">{userVerificationRate}%</span>
                                <span className="text-sm text-gray-500 mb-1">users phone verified</span>
                            </div>
                            <div className="w-full bg-gray-100 rounded-full h-2 mt-4">
                                <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${userVerificationRate}%` }}></div>
                            </div>
                        </Card>

                        <Card className="p-6 bg-red-50 border border-red-100">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="font-bold text-red-800">Active Issues</h3>
                                <Flag className="text-red-600 w-6 h-6" />
                            </div>
                            <div className="flex items-end gap-2">
                                <span className="text-4xl font-extrabold text-red-900">{activeFlags.length + pendingReminders.length}</span>
                                <span className="text-sm text-red-700/80 mb-1">require attention</span>
                            </div>
                            <p className="text-xs text-red-600 mt-4">Flags: {activeFlags.length} | Reminders: {pendingReminders.length}</p>
                        </Card>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Flagged Venues */}
                        <Card className="p-0 overflow-hidden h-fit">
                            <div className="p-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
                                <h3 className="font-bold text-gray-900 flex items-center gap-2">
                                    <Building2 className="w-4 h-4 text-gray-500" /> Venue Risks
                                </h3>
                                <Badge variant="error">{flaggedVenues.length} Issues</Badge>
                            </div>
                            <table className="w-full text-left text-sm text-gray-500">
                                <thead className="bg-white text-xs uppercase text-gray-700 font-semibold border-b">
                                    <tr>
                                        <th className="px-6 py-3">Venue</th>
                                        <th className="px-6 py-3">Issue</th>
                                        <th className="px-6 py-3">Action</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100">
                                    {loading ? (
                                        <tr><td colSpan={3} className="px-6 py-4 text-center">Scanning...</td></tr>
                                    ) : flaggedVenues.slice(0, 5).map(v => (
                                        <tr key={v.id}>
                                            <td className="px-6 py-4 font-medium text-gray-900">{v.name}</td>
                                            <td className="px-6 py-4">
                                                <div className="flex flex-wrap gap-1">
                                                    {!v.contactPhone && <Badge variant="warning">No Phone</Badge>}
                                                    {!v.imageUrl && <Badge variant="warning">No Image</Badge>}
                                                    {(!v.description || v.description.length <= 5) && <Badge variant="warning">Weak Desc</Badge>}
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    className="text-red-600 border-red-200 hover:bg-red-50"
                                                    onClick={() => handleFlagVenueClick(v)}
                                                    isLoading={actionLoading === v.id}
                                                >
                                                    Flag
                                                </Button>
                                            </td>
                                        </tr>
                                    ))}
                                    {flaggedVenues.length === 0 && !loading && (
                                        <tr><td colSpan={3} className="px-6 py-8 text-center text-green-600">All venues compliant.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </Card>

                        {/* Unverified Users */}
                        <Card className="p-0 overflow-hidden h-fit">
                            <div className="p-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
                                <h3 className="font-bold text-gray-900 flex items-center gap-2">
                                    <Users className="w-4 h-4 text-gray-500" /> Identity Checks
                                </h3>
                                <Badge variant="warning">{unverifiedUsers.length} Unverified</Badge>
                            </div>
                            <table className="w-full text-left text-sm text-gray-500">
                                <thead className="bg-white text-xs uppercase text-gray-700 font-semibold border-b">
                                    <tr>
                                        <th className="px-6 py-3">User</th>
                                        <th className="px-6 py-3">Missing</th>
                                        <th className="px-6 py-3">Action</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100">
                                    {unverifiedUsers.slice(0, 5).map(u => (
                                        <tr key={u.id}>
                                            <td className="px-6 py-4">
                                                <div className="font-medium text-gray-900">{u.name}</div>
                                                <div className="text-xs">{u.email}</div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className="text-xs font-mono bg-gray-100 px-2 py-1 rounded">Phone Number</span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    className="text-indigo-600"
                                                    onClick={() => handleRemindUser(u)}
                                                    isLoading={actionLoading === u.id}
                                                >
                                                    Remind
                                                </Button>
                                            </td>
                                        </tr>
                                    ))}
                                    {unverifiedUsers.length === 0 && (
                                        <tr><td colSpan={3} className="px-6 py-8 text-center text-green-600">All users verified.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </Card>
                    </div>
                </>
            )}

            {activeTab === 'flags' && (
                <Card className="p-0 overflow-hidden">
                    <div className="p-4 border-b border-gray-100 bg-gray-50">
                        <h3 className="font-bold text-gray-900">All Trust Flags</h3>
                    </div>
                    <table className="w-full text-left text-sm">
                        <thead className="bg-gray-50 text-xs uppercase text-gray-700 font-semibold border-b">
                            <tr>
                                <th className="px-6 py-3">Entity</th>
                                <th className="px-6 py-3">Flag Type</th>
                                <th className="px-6 py-3">Status</th>
                                <th className="px-6 py-3">Raised</th>
                                <th className="px-6 py-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {flags.length === 0 ? (
                                <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-500">No flags recorded.</td></tr>
                            ) : flags.map(flag => (
                                <tr key={flag.id}>
                                    <td className="px-6 py-4">
                                        <div className="font-medium text-gray-900">{flag.entity_name}</div>
                                        <div className="text-xs text-gray-500">{flag.entity_type}</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant="warning">{flag.flag_type?.replace('_', ' ')}</Badge>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant={flag.status === 'active' ? 'error' : flag.status === 'resolved' ? 'success' : 'warning'}>
                                            {flag.status}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4 text-xs text-gray-500">
                                        {new Date(flag.created_at).toLocaleDateString()}
                                    </td>
                                    <td className="px-6 py-4">
                                        {(flag.status === 'active' || flag.status === 'owner_resubmitted') && (
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => { setSelectedFlag(flag); setResolveModalOpen(true); }}
                                            >
                                                Resolve
                                            </Button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {activeTab === 'reminders' && (
                <Card className="p-0 overflow-hidden">
                    <div className="p-4 border-b border-gray-100 bg-gray-50">
                        <h3 className="font-bold text-gray-900">All Reminders</h3>
                    </div>
                    <table className="w-full text-left text-sm">
                        <thead className="bg-gray-50 text-xs uppercase text-gray-700 font-semibold border-b">
                            <tr>
                                <th className="px-6 py-3">User</th>
                                <th className="px-6 py-3">Type</th>
                                <th className="px-6 py-3">Status</th>
                                <th className="px-6 py-3">Blocks</th>
                                <th className="px-6 py-3">Sent</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {reminders.length === 0 ? (
                                <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-500">No reminders sent.</td></tr>
                            ) : reminders.map(r => (
                                <tr key={r.id}>
                                    <td className="px-6 py-4">
                                        <div className="font-medium text-gray-900">{r.user_name}</div>
                                        <div className="text-xs text-gray-500">{r.user_email}</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant="info">{r.reminder_type}</Badge>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant={r.status === 'pending' ? 'warning' : r.status === 'completed' ? 'success' : 'info'}>
                                            {r.status}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4 text-xs">
                                        {r.blocks_listings && <span className="bg-red-100 text-red-700 px-1 rounded mr-1">Listings</span>}
                                        {r.blocks_payments && <span className="bg-red-100 text-red-700 px-1 rounded mr-1">Payments</span>}
                                        {r.blocks_bookings && <span className="bg-red-100 text-red-700 px-1 rounded">Bookings</span>}
                                    </td>
                                    <td className="px-6 py-4 text-xs text-gray-500">
                                        {new Date(r.sent_at).toLocaleDateString()}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {activeTab === 'audit' && (
                <Card className="p-0 overflow-hidden">
                    <div className="p-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
                        <h3 className="font-bold text-gray-900">Audit Log ({auditTotal} entries)</h3>
                        <div className="flex gap-2">
                            <select
                                className="text-sm border rounded px-2 py-1"
                                value={auditActionFilter}
                                onChange={(e) => setAuditActionFilter(e.target.value)}
                            >
                                <option value="">All Actions</option>
                                <option value="flag_raised">Flag Raised</option>
                                <option value="flag_resolved">Flag Resolved</option>
                                <option value="reminder_sent">Reminder Sent</option>
                                <option value="owner_resubmitted">Owner Resubmitted</option>
                            </select>
                            <select
                                className="text-sm border rounded px-2 py-1"
                                value={auditEntityFilter}
                                onChange={(e) => setAuditEntityFilter(e.target.value)}
                            >
                                <option value="">All Entities</option>
                                <option value="reading_room">Reading Room</option>
                                <option value="accommodation">Accommodation</option>
                                <option value="user">User</option>
                            </select>
                        </div>
                    </div>
                    <table className="w-full text-left text-sm">
                        <thead className="bg-gray-50 text-xs uppercase text-gray-700 font-semibold border-b">
                            <tr>
                                <th className="px-6 py-3">Timestamp</th>
                                <th className="px-6 py-3">Actor</th>
                                <th className="px-6 py-3">Action</th>
                                <th className="px-6 py-3">Entity</th>
                                <th className="px-6 py-3">Description</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {auditLog.length === 0 ? (
                                <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-500">No audit entries found.</td></tr>
                            ) : auditLog.map(entry => (
                                <tr key={entry.id}>
                                    <td className="px-6 py-4 text-xs text-gray-500">
                                        {new Date(entry.timestamp).toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="font-medium text-gray-900">{entry.actor_name}</div>
                                        <div className="text-xs text-gray-500">{entry.actor_role}</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant="info">{entry.action_type?.replace('_', ' ')}</Badge>
                                    </td>
                                    <td className="px-6 py-4 text-xs">
                                        {entry.entity_name && <div className="font-medium">{entry.entity_name}</div>}
                                        <div className="text-gray-500">{entry.entity_type}</div>
                                    </td>
                                    <td className="px-6 py-4 text-xs text-gray-600 max-w-xs truncate">
                                        {entry.action_description}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {/* Resolve Modal - Simplified */}
            {resolveModalOpen && selectedFlag && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                    <Card className="w-full max-w-md p-6 bg-white animate-in zoom-in-95">
                        <h3 className="text-xl font-bold mb-4">Resolve Flag</h3>
                        <div className="bg-gray-50 p-3 rounded mb-4 text-sm">
                            <div className="flex justify-between items-start mb-1">
                                <p className="font-bold text-gray-900">{selectedFlag.entity_name}</p>
                                <Badge variant="warning">{selectedFlag.flag_type?.replace(/_/g, ' ')}</Badge>
                            </div>
                            <p className="text-gray-600 mb-2">
                                <span className="font-semibold">Reason:</span> {selectedFlag.custom_reason || 'No specific reason provided.'}
                            </p>

                            {/* OWNER NOTES - CRITICAL FIX */}
                            {selectedFlag.owner_notes && (
                                <div className="mt-3 bg-blue-50 p-3 rounded border border-blue-100 animate-in fade-in">
                                    <p className="text-xs font-bold text-blue-700 uppercase tracking-wider mb-1">
                                        Owner's Appeal / Message
                                    </p>
                                    <p className="text-blue-900 whitespace-pre-wrap text-sm">
                                        "{selectedFlag.owner_notes}"
                                    </p>
                                </div>
                            )}
                        </div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Resolution Notes (Internal)</label>
                        <textarea
                            className="w-full border rounded p-2 text-sm mb-4 h-24"
                            placeholder="Add internal notes about this resolution..."
                            value={resolveNotes}
                            onChange={(e) => setResolveNotes(e.target.value)}
                        />
                        <div className="flex gap-2 justify-end">
                            <Button variant="outline" onClick={() => setResolveModalOpen(false)}>Cancel</Button>
                            <Button variant="danger" onClick={() => handleResolveFlag('reject')}>Reject</Button>
                            <Button variant="primary" onClick={() => handleResolveFlag('approve')}>Resolve (Approve)</Button>
                        </div>
                    </Card>
                </div>
            )}

            {/* Create Flag Modal */}
            {flagModalOpen && selectedVenue && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                    <Card className="w-full max-w-md p-6 bg-white animate-in zoom-in-95">
                        <div className="flex items-start gap-4 mb-4">
                            <div className="bg-red-100 p-2 rounded-lg">
                                <Flag className="text-red-600 w-6 h-6" />
                            </div>
                            <div>
                                <h3 className="text-xl font-bold text-gray-900">Flag for Compliance</h3>
                                <p className="text-sm text-gray-500">Restrict listing visibility for {selectedVenue.name}</p>
                            </div>
                        </div>

                        <div className="mb-4">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Reason for Non-Compliance</label>
                            <textarea
                                className="w-full border border-gray-300 rounded-lg p-3 text-sm h-32 focus:ring-2 focus:ring-red-500 focus:border-transparent outline-none"
                                placeholder="Describe exactly what is missing or incorrect. The owner will see this message."
                                value={flagReason}
                                onChange={(e) => setFlagReason(e.target.value)}
                                autoFocus
                            />
                            <p className="text-xs text-gray-500 mt-1">
                                Be specific. This helps the owner resolve the issue faster.
                            </p>
                        </div>

                        <div className="flex gap-2 justify-end">
                            <Button variant="outline" onClick={() => setFlagModalOpen(false)}>Cancel</Button>
                            <Button variant="danger" onClick={confirmFlagVenue} disabled={!flagReason.trim()}>
                                Create Flag
                            </Button>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
};
