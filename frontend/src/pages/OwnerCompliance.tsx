import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, AppState, ReadingRoom, Accommodation } from '../types';
import { Card, Button, Badge, Modal, Input } from '../components/UI';
import {
    ArrowLeft, Shield, User as UserIcon, Mail, Phone, Building2,
    MapPin, CheckCircle, Clock, AlertTriangle, FileText, History,
    Lock, Eye, ChevronRight, AlertOctagon, RefreshCw
} from 'lucide-react';
import { trustService, TrustFlag } from '../services/trustService';

interface OwnerComplianceProps {
    state: AppState;
    user: User;
    onUpdateUser: (data: Partial<User>) => void;
}

export const OwnerCompliance: React.FC<OwnerComplianceProps> = ({ state, user, onUpdateUser }) => {
    const navigate = useNavigate();
    const [isEditIdentityOpen, setIsEditIdentityOpen] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Trust & Safety State
    const [trustFlags, setTrustFlags] = useState<TrustFlag[]>([]);
    const [isLoadingFlags, setIsLoadingFlags] = useState(true);
    const [isResolveModalOpen, setIsResolveModalOpen] = useState(false);
    const [selectedFlag, setSelectedFlag] = useState<TrustFlag | null>(null);
    const [resolutionNotes, setResolutionNotes] = useState('');
    const [isResubmitting, setIsResubmitting] = useState(false);

    // Get owner's venues for business type info
    const myVenues = state.readingRooms.filter(r => r.ownerId === user.id);
    const myAccommodations = state.accommodations.filter(a => a.ownerId === user.id);

    // Derive business info from venues
    const businessType = myVenues.length > 0 ? 'Reading Room' : myAccommodations.length > 0 ? 'PG/Hostel' : 'Not Registered';
    const operatingCity = myVenues[0]?.city || myAccommodations[0]?.city || 'Not Set';
    const isVerified = myVenues.some(v => v.isVerified) || myAccommodations.some(a => a.isVerified);

    // Fetch Trust Flags for Owner
    useEffect(() => {
        const fetchFlags = async () => {
            try {
                setIsLoadingFlags(true);
                const flags = await trustService.getOwnerFlags(user.id);
                setTrustFlags(flags);
            } catch (err) {
                console.error('Failed to fetch trust flags:', err);
            } finally {
                setIsLoadingFlags(false);
            }
        };
        fetchFlags();
    }, [user.id]);

    // Active flags that need owner attention
    const activeFlags = trustFlags.filter(f => f.status === 'active');
    const resubmittedFlags = trustFlags.filter(f => f.status === 'owner_resubmitted');
    const escalatedFlags = trustFlags.filter(f => f.status === 'escalated');
    const resolvedFlags = trustFlags.filter(f => f.status === 'resolved');

    // Handle owner resubmit
    const handleResubmit = async () => {
        if (!selectedFlag || !resolutionNotes.trim()) return;

        setIsResubmitting(true);
        try {
            await trustService.ownerResubmit(selectedFlag.id, resolutionNotes, user.id, user.name);
            // Update local state
            setTrustFlags(prev => prev.map(f =>
                f.id === selectedFlag.id
                    ? { ...f, status: 'owner_resubmitted' as const, owner_notes: resolutionNotes }
                    : f
            ));
            setIsResolveModalOpen(false);
            setSelectedFlag(null);
            setResolutionNotes('');
        } catch (err) {
            console.error('Failed to resubmit:', err);
        } finally {
            setIsResubmitting(false);
        }
    };

    // Mock verification history
    const verificationHistory = [
        { date: '2024-01-15', action: 'Account Created', status: 'success' },
        { date: '2024-01-18', action: 'Documents Submitted', status: 'info' },
        { date: '2024-01-22', action: 'Verification Approved', status: 'success' },
    ];

    const getVerificationBadge = () => {
        switch (user.verificationStatus) {
            case 'VERIFIED':
                return <Badge variant="success"><CheckCircle className="w-3 h-3 mr-1" /> Verified</Badge>;
            case 'PENDING':
                return <Badge variant="warning"><Clock className="w-3 h-3 mr-1" /> Pending Review</Badge>;
            case 'REJECTED':
                return <Badge variant="danger"><AlertTriangle className="w-3 h-3 mr-1" /> Rejected</Badge>;
            default:
                return <Badge variant="secondary"><Clock className="w-3 h-3 mr-1" /> Not Submitted</Badge>;
        }
    };

    const InfoRow = ({ icon: Icon, label, value, verified = false }: { icon: any, label: string, value: string, verified?: boolean }) => (
        <div className="flex items-start justify-between py-3 border-b border-gray-100 last:border-none">
            <div className="flex items-center gap-3">
                <div className="p-2 bg-gray-50 rounded-lg">
                    <Icon className="w-4 h-4 text-gray-500" />
                </div>
                <div>
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className="font-medium text-gray-900">{value}</p>
                </div>
            </div>
            {verified && <CheckCircle className="w-5 h-5 text-green-500" />}
        </div>
    );

    return (
        <div className="max-w-3xl mx-auto pb-10">
            {/* Header */}
            <div className="mb-6">
                <button
                    onClick={() => navigate('/admin/profile')}
                    className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4 mr-1" /> Back to Profile
                </button>
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">Account & Compliance</h1>
                        <p className="text-gray-500 mt-1">Manage your owner identity and verification status</p>
                    </div>
                    {getVerificationBadge()}
                </div>
            </div>

            {/* Owner Identity */}
            <Card className="p-6 mb-6">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <UserIcon className="w-5 h-5 text-indigo-600" />
                        <h3 className="text-lg font-bold text-gray-900">Owner Identity</h3>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => setIsEditIdentityOpen(true)}>
                        Edit
                    </Button>
                </div>

                <div className="space-y-1">
                    <InfoRow icon={UserIcon} label="Owner Name" value={user.name} verified={!!user.name} />
                    <InfoRow icon={Mail} label="Email Address" value={user.email} verified={true} />
                    <InfoRow icon={Phone} label="Phone Number" value={user.phone || 'Not provided'} verified={!!user.phone} />
                </div>
            </Card>

            {/* Business Compliance */}
            <Card className="p-6 mb-6">
                <div className="flex items-center gap-2 mb-4">
                    <Shield className="w-5 h-5 text-indigo-600" />
                    <h3 className="text-lg font-bold text-gray-900">Business Compliance</h3>
                </div>

                <div className="space-y-1">
                    <InfoRow icon={Building2} label="Business Type" value={businessType} />
                    <InfoRow icon={FileText} label="Registered Business" value={myVenues[0]?.name || myAccommodations[0]?.name || 'No venue registered'} />
                    <InfoRow icon={MapPin} label="Operating Region" value={operatingCity} />
                </div>

                <div className="mt-4 p-4 bg-gray-50 rounded-lg border">
                    <div className="flex items-start gap-3">
                        <div className="p-2 bg-white rounded-lg shadow-sm">
                            <Shield className="w-5 h-5 text-indigo-600" />
                        </div>
                        <div className="flex-1">
                            <p className="font-medium text-gray-900">Verification Status</p>
                            <p className="text-sm text-gray-500 mb-2">
                                {isVerified
                                    ? 'Your business is verified and live on StudySpace'
                                    : 'Complete verification to go live on StudySpace'}
                            </p>
                            {getVerificationBadge()}
                        </div>
                    </div>
                </div>

                <div className="mt-4 p-3 bg-amber-50 rounded-lg border border-amber-100">
                    <p className="text-sm text-amber-700">
                        <AlertTriangle className="w-4 h-4 inline mr-1" />
                        Changes to business details require admin re-verification
                    </p>
                </div>
            </Card>

            {/* Trust & Safety Section */}
            <Card className="p-6 mb-6">
                <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                        <AlertOctagon className="w-5 h-5 text-indigo-600" />
                        <h3 className="text-lg font-bold text-gray-900">Trust & Safety</h3>
                    </div>
                    {isLoadingFlags ? (
                        <Badge variant="secondary"><RefreshCw className="w-3 h-3 mr-1 animate-spin" /> Loading...</Badge>
                    ) : escalatedFlags.length > 0 ? (
                        <Badge variant="danger">{escalatedFlags.length} Suspended</Badge>
                    ) : activeFlags.length > 0 ? (
                        <Badge variant="danger">{activeFlags.length} Action Required</Badge>
                    ) : resubmittedFlags.length > 0 ? (
                        <Badge variant="warning">{resubmittedFlags.length} Under Review</Badge>
                    ) : (
                        <Badge variant="success"><CheckCircle className="w-3 h-3 mr-1" /> All Clear</Badge>
                    )}
                </div>

                {/* Active Flags - Action Required */}
                {activeFlags.length > 0 && (
                    <div className="mb-4 p-4 bg-red-50 rounded-lg border border-red-200">
                        <h4 className="font-bold text-red-800 mb-3 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4" /> Action Required
                        </h4>
                        <div className="space-y-3">
                            {activeFlags.map(flag => (
                                <div key={flag.id} className="bg-white p-3 rounded border border-red-100">
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <p className="font-medium text-gray-900">{flag.entity_name}</p>
                                            <p className="text-sm text-red-600">
                                                Issue: {flag.flag_type?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                            </p>
                                            {flag.custom_reason && (
                                                <p className="text-sm text-gray-600 mt-1">{flag.custom_reason}</p>
                                            )}
                                            <p className="text-xs text-gray-400 mt-1">
                                                Flagged on {new Date(flag.created_at).toLocaleDateString()}
                                            </p>
                                        </div>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="text-red-600 border-red-200"
                                            onClick={() => {
                                                setSelectedFlag(flag);
                                                setIsResolveModalOpen(true);
                                            }}
                                        >
                                            Resolve
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                        <p className="text-xs text-red-600 mt-3">
                            ⚠️ Promotions and boosts are disabled until issues are resolved.
                        </p>
                    </div>
                )}

                {/* ESCALATED Flags - Venue Suspended */}
                {escalatedFlags.length > 0 && (
                    <div className="mb-4 p-4 bg-red-100 rounded-lg border-2 border-red-300">
                        <h4 className="font-bold text-red-900 mb-3 flex items-center gap-2">
                            <AlertOctagon className="w-5 h-5" /> Venue Suspended
                        </h4>
                        <div className="space-y-3">
                            {escalatedFlags.map(flag => (
                                <div key={flag.id} className="bg-white p-4 rounded border border-red-200">
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <p className="font-bold text-gray-900 text-lg">{flag.entity_name}</p>
                                            <p className="text-red-700 font-medium">
                                                Suspended: {flag.flag_type?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                            </p>
                                            {flag.custom_reason && (
                                                <p className="text-gray-700 mt-2">"{flag.custom_reason}"</p>
                                            )}
                                            <p className="text-sm text-gray-500 mt-2">
                                                Suspended on {new Date(flag.created_at).toLocaleDateString()}
                                            </p>
                                        </div>
                                        <Badge variant="danger">Suspended</Badge>
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="mt-4 p-3 bg-white rounded border border-red-200">
                            <p className="text-sm text-red-800">
                                <strong>⛔ Your venue has been suspended by admin.</strong><br />
                                This venue is not visible to users. Contact support for resolution.
                            </p>
                        </div>
                    </div>
                )}

                {/* Resubmitted Flags - Under Review */}
                {resubmittedFlags.length > 0 && (
                    <div className="mb-4 p-4 bg-amber-50 rounded-lg border border-amber-200">
                        <h4 className="font-bold text-amber-800 mb-3 flex items-center gap-2">
                            <Clock className="w-4 h-4" /> Under Review
                        </h4>
                        <div className="space-y-2">
                            {resubmittedFlags.map(flag => (
                                <div key={flag.id} className="flex items-center justify-between bg-white p-3 rounded border border-amber-100">
                                    <div>
                                        <p className="font-medium text-gray-900">{flag.entity_name}</p>
                                        <p className="text-sm text-amber-600">
                                            Awaiting admin approval
                                        </p>
                                    </div>
                                    <Badge variant="warning">Pending</Badge>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* All Clear State */}
                {activeFlags.length === 0 && resubmittedFlags.length === 0 && escalatedFlags.length === 0 && !isLoadingFlags && (
                    <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-green-100 rounded-full">
                                <CheckCircle className="w-5 h-5 text-green-600" />
                            </div>
                            <div>
                                <p className="font-medium text-green-800">No Issues Detected</p>
                                <p className="text-sm text-green-600">
                                    Your venues are in good standing. Promotions and boosts are available.
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Resolved History */}
                {resolvedFlags.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-100">
                        <p className="text-sm text-gray-500 mb-2">Recently resolved:</p>
                        <div className="space-y-1">
                            {resolvedFlags.slice(0, 3).map(flag => (
                                <div key={flag.id} className="flex items-center gap-2 text-sm text-gray-600">
                                    <CheckCircle className="w-3 h-3 text-green-500" />
                                    <span>{flag.entity_name} - {flag.flag_type?.replace(/_/g, ' ')}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </Card>

            {/* Verification History */}
            <Card className="p-6">
                <div className="flex items-center gap-2 mb-4">
                    <History className="w-5 h-5 text-indigo-600" />
                    <h3 className="text-lg font-bold text-gray-900">Verification History</h3>
                </div>

                <div className="space-y-3">
                    {verificationHistory.map((item, index) => (
                        <div key={index} className="flex items-center gap-3 py-2">
                            <div className={`w-2 h-2 rounded-full ${item.status === 'success' ? 'bg-green-500' :
                                item.status === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'
                                }`} />
                            <div className="flex-1">
                                <p className="text-sm font-medium text-gray-900">{item.action}</p>
                                <p className="text-xs text-gray-500">{item.date}</p>
                            </div>
                            <CheckCircle className={`w-4 h-4 ${item.status === 'success' ? 'text-green-500' : 'text-gray-300'
                                }`} />
                        </div>
                    ))}
                </div>
            </Card>

            {/* Edit Identity Modal */}
            <Modal
                isOpen={isEditIdentityOpen}
                onClose={() => setIsEditIdentityOpen(false)}
                title="Edit Owner Identity"
            >
                <form onSubmit={(e) => {
                    e.preventDefault();
                    setIsSubmitting(true);
                    const formData = new FormData(e.currentTarget);
                    setTimeout(() => {
                        onUpdateUser({
                            name: formData.get('name') as string,
                            phone: formData.get('phone') as string,
                        });
                        setIsSubmitting(false);
                        setIsEditIdentityOpen(false);
                    }, 800);
                }} className="space-y-4 py-2">
                    <Input label="Owner Name" name="name" defaultValue={user.name} required />
                    <div className="relative">
                        <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                        <input
                            className="w-full px-3 py-2 border border-gray-200 bg-gray-50 text-gray-500 rounded-lg"
                            value={user.email}
                            readOnly
                        />
                        <Lock className="w-4 h-4 text-gray-400 absolute right-3 top-9" />
                        <p className="text-xs text-gray-500 mt-1">Email changes require re-verification</p>
                    </div>
                    <Input label="Phone Number" name="phone" defaultValue={user.phone || ''} placeholder="+91..." />

                    <div className="pt-4 flex gap-3">
                        <Button type="button" variant="ghost" className="flex-1" onClick={() => setIsEditIdentityOpen(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" className="flex-1" isLoading={isSubmitting}>
                            Save Changes
                        </Button>
                    </div>
                </form>
            </Modal>

            {/* Resolution Modal */}
            <Modal
                isOpen={isResolveModalOpen}
                onClose={() => {
                    setIsResolveModalOpen(false);
                    setSelectedFlag(null);
                    setResolutionNotes('');
                }}
                title="Resolve Trust Issue"
            >
                <div className="py-2">
                    {selectedFlag && (
                        <>
                            <div className="mb-4 p-3 bg-red-50 rounded-lg border border-red-200">
                                <p className="font-medium text-red-800">{selectedFlag.entity_name}</p>
                                <p className="text-sm text-red-600">
                                    Issue: {selectedFlag.flag_type?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                </p>
                                {selectedFlag.custom_reason && (
                                    <p className="text-sm text-gray-600 mt-1">{selectedFlag.custom_reason}</p>
                                )}
                            </div>

                            <div className="mb-4">
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    How did you resolve this issue?
                                </label>
                                <textarea
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                                    rows={4}
                                    placeholder="Describe the changes you made to address this issue..."
                                    value={resolutionNotes}
                                    onChange={(e) => setResolutionNotes(e.target.value)}
                                />
                            </div>

                            <div className="p-3 bg-blue-50 rounded-lg border border-blue-200 mb-4">
                                <p className="text-sm text-blue-700">
                                    <strong>Note:</strong> After submission, an admin will review your changes.
                                    Promotions will remain disabled until approved.
                                </p>
                            </div>

                            <div className="flex gap-3 pt-2">
                                <Button
                                    variant="ghost"
                                    className="flex-1"
                                    onClick={() => {
                                        setIsResolveModalOpen(false);
                                        setSelectedFlag(null);
                                        setResolutionNotes('');
                                    }}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    className="flex-1"
                                    isLoading={isResubmitting}
                                    onClick={handleResubmit}
                                    disabled={!resolutionNotes.trim()}
                                >
                                    Submit for Review
                                </Button>
                            </div>
                        </>
                    )}
                </div>
            </Modal>
        </div>
    );
};

export default OwnerCompliance;
