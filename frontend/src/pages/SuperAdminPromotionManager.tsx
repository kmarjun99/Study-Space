
import React, { useState, useEffect } from 'react';
import { BoostPlan, BoostRequest } from '../services/boostService';
import { boostService } from '../services/boostService';
import { Card, Button, Input, Badge, Modal } from '../components/UI';
import { Sparkles, CheckCircle, Lock, Trash2, Plus } from 'lucide-react';

export const SuperAdminPromotionManager: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'PLANS' | 'PENDING' | 'ACTIVE' | 'HISTORY'>('PLANS');
    const [plans, setPlans] = useState<BoostPlan[]>([]);
    const [requests, setRequests] = useState<BoostRequest[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isEditorOpen, setIsEditorOpen] = useState(false);
    const [editingPlan, setEditingPlan] = useState<Partial<BoostPlan>>({
        name: '', description: '', durationDays: 7, price: 499,
        status: 'draft', applicableTo: 'both', placement: 'featured_section'
    });

    // Load data from API on mount
    useEffect(() => {
        const loadData = async () => {
            setIsLoading(true);
            try {
                const [plansData, requestsData] = await Promise.all([
                    boostService.getPlans(true), // Include inactive for super admin
                    boostService.getAllRequests()
                ]);
                setPlans(plansData);
                setRequests(requestsData);
            } catch (error) {
                console.error('Failed to load boost data:', error);
            } finally {
                setIsLoading(false);
            }
        };
        loadData();
    }, []);

    const pendingRequests = requests.filter(r => ['payment_pending', 'initiated', 'paid', 'admin_review'].includes(r.status.toLowerCase()));
    const activeRequests = requests.filter(r => r.status === 'approved' && (!r.expiryDate || new Date(r.expiryDate) > new Date()));
    const historyRequests = requests.filter(r => r.status === 'rejected' || r.status === 'expired' || (r.status === 'approved' && r.expiryDate && new Date(r.expiryDate) <= new Date()));

    const handleSavePlan = async () => {
        if (!editingPlan.name || !editingPlan.price || editingPlan.price <= 0 || !editingPlan.durationDays) {
            alert('Please enter valid name, price, and duration.');
            return;
        }

        try {
            if (editingPlan.id) {
                // Update existing plan
                const updated = await boostService.updatePlan(editingPlan.id, editingPlan);
                setPlans(plans.map(p => p.id === updated.id ? updated : p));
            } else {
                // Create new plan
                const created = await boostService.createPlan(editingPlan);
                setPlans([...plans, created]);
            }
            setIsEditorOpen(false);
            setEditingPlan({ name: '', description: '', durationDays: 7, price: 499, status: 'draft', applicableTo: 'both', placement: 'featured_section' });
        } catch (error: any) {
            console.error('Failed to save plan:', error);
            const errorMsg = error.response?.data?.detail || error.message || 'Unknown error';
            alert(`Failed to save plan: ${errorMsg}`);
        }
    };

    const handleTogglePlanStatus = async (planId: string, newStatus: 'draft' | 'active' | 'inactive') => {
        try {
            const updated = await boostService.updatePlan(planId, { status: newStatus });
            setPlans(plans.map(p => p.id === planId ? updated : p));
        } catch (error) {
            console.error('Failed to update plan status:', error);
            alert('Failed to update status.');
        }
    };

    const handleDeletePlan = async (planId: string) => {
        if (!confirm('Delete this promotion plan?')) return;
        try {
            await boostService.deletePlan(planId);
            setPlans(plans.filter(p => p.id !== planId));
        } catch (error) {
            console.error('Failed to delete plan:', error);
            alert('Failed to delete plan.');
        }
    };

    const handleApprove = async (requestId: string) => {
        try {
            await boostService.approveRequest(requestId);
            // Reload requests
            const updatedRequests = await boostService.getAllRequests();
            setRequests(updatedRequests);
            alert('Request approved! Listing is now promoted.');
        } catch (error) {
            console.error('Failed to approve:', error);
            alert('Failed to approve request.');
        }
    };

    const handleReject = async (requestId: string) => {
        const reason = prompt('Enter rejection reason:');
        if (!reason) return;
        try {
            await boostService.rejectRequest(requestId, reason);
            // Reload requests
            const updatedRequests = await boostService.getAllRequests();
            setRequests(updatedRequests);
            alert('Request rejected.');
        } catch (error) {
            console.error('Failed to reject:', error);
            alert('Failed to reject request.');
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div>
                <h2 className="text-2xl font-bold text-gray-900">Promotions</h2>
                <p className="text-gray-500">Manage promotion plans and approve owner requests.</p>
            </div>

            <div className="flex gap-2 mb-6 border-b border-gray-200 pb-4">
                {(['PLANS', 'PENDING', 'ACTIVE', 'HISTORY'] as const).map(tab => (
                    <Button key={tab} variant={activeTab === tab ? 'primary' : 'outline'} onClick={() => setActiveTab(tab)}>
                        {tab === 'PLANS' && 'Plans'}
                        {tab === 'PENDING' && <>Pending <Badge variant="warning" className="ml-1">{pendingRequests.length}</Badge></>}
                        {tab === 'ACTIVE' && <>Active <Badge variant="success" className="ml-1">{activeRequests.length}</Badge></>}
                        {tab === 'HISTORY' && 'History'}
                    </Button>
                ))}
            </div>

            {activeTab === 'PLANS' && (
                <div className="space-y-6">
                    <div className="flex justify-between items-center">
                        <p className="text-gray-500">Create promotion plans that venue owners can purchase.</p>
                        <Button onClick={() => { setEditingPlan({ name: '', description: '', durationDays: 7, price: 499, status: 'draft', applicableTo: 'both', placement: 'featured_section' }); setIsEditorOpen(true); }}>
                            <Plus className="w-4 h-4 mr-2" /> Create Plan
                        </Button>
                    </div>
                    {plans.length === 0 ? (
                        <Card className="p-12 text-center">
                            <Sparkles className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                            <h3 className="text-lg font-bold text-gray-700 mb-2">No Promotion Plans</h3>
                            <p className="text-gray-500 mb-4">Owners cannot promote listings until you create a plan.</p>
                            <Button onClick={() => setIsEditorOpen(true)}><Plus className="w-4 h-4 mr-2" /> Create First Plan</Button>
                        </Card>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            {plans.map(plan => (
                                <Card key={plan.id} className={`border-t-4 ${plan.status === 'active' ? 'border-t-green-500' : plan.status === 'draft' ? 'border-t-yellow-500' : 'border-t-gray-300'}`}>
                                    <div className="p-6">
                                        <div className="flex justify-between items-start mb-3">
                                            <Badge variant={plan.status === 'active' ? 'success' : plan.status === 'draft' ? 'warning' : 'info'}>{plan.status}</Badge>
                                            <div className="flex gap-1">
                                                {plan.status !== 'active' && <button onClick={() => handleTogglePlanStatus(plan.id, 'active')} className="p-1 text-gray-400 hover:text-green-600" title="Activate"><CheckCircle className="w-4 h-4" /></button>}
                                                {plan.status === 'active' && <button onClick={() => handleTogglePlanStatus(plan.id, 'inactive')} className="p-1 text-gray-400 hover:text-orange-600" title="Deactivate"><Lock className="w-4 h-4" /></button>}
                                                <button onClick={() => handleDeletePlan(plan.id)} className="p-1 text-gray-400 hover:text-red-600" title="Delete"><Trash2 className="w-4 h-4" /></button>
                                            </div>
                                        </div>
                                        <h3 className="text-xl font-bold text-gray-900">{plan.name}</h3>
                                        <p className="text-sm text-gray-500 mt-1">{plan.description}</p>
                                        <div className="mt-3 flex flex-wrap gap-2">
                                            <Badge variant="info">{plan.placement.replace('_', ' ')}</Badge>
                                            <Badge variant="info">{plan.applicableTo}</Badge>
                                        </div>
                                        <div className="mt-4 flex items-baseline">
                                            <span className="text-3xl font-extrabold text-indigo-600">₹{plan.price}</span>
                                            <span className="ml-1 text-gray-500">/ {plan.durationDays} days <span className="text-xs">+ GST</span></span>
                                        </div>
                                    </div>
                                    <div className="p-4 bg-gray-50 border-t">
                                        <Button size="sm" variant="outline" onClick={() => { setEditingPlan(plan); setIsEditorOpen(true); }}>Edit</Button>
                                    </div>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {(activeTab === 'PENDING' || activeTab === 'ACTIVE' || activeTab === 'HISTORY') && (
                <Card className="p-0 overflow-hidden border border-gray-200 shadow-sm">
                    <table className="w-full text-left text-sm text-gray-500">
                        <thead className="bg-gray-50 text-xs uppercase text-gray-700 font-semibold border-b">
                            <tr>
                                <th className="px-6 py-4">Listing</th>
                                <th className="px-6 py-4">Owner</th>
                                <th className="px-6 py-4">Plan</th>
                                <th className="px-6 py-4">Payment</th>
                                <th className="px-6 py-4">Status</th>
                                <th className="px-6 py-4 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {(activeTab === 'PENDING' ? pendingRequests : activeTab === 'ACTIVE' ? activeRequests : historyRequests).length === 0 ? (
                                <tr><td colSpan={6} className="px-6 py-12 text-center text-gray-400">No requests found.</td></tr>
                            ) : (activeTab === 'PENDING' ? pendingRequests : activeTab === 'ACTIVE' ? activeRequests : historyRequests).map(item => (
                                <tr key={item.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4">
                                        <div className="font-bold text-gray-900">{item.venueName || 'Unknown Venue'}</div>
                                        <Badge variant="info">{item.venueType}</Badge>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="font-medium text-gray-900">{item.ownerName}</div>
                                        <div className="text-xs text-gray-500">{(item as any).ownerEmail}</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className="font-semibold text-indigo-600">{item.planName || 'Boost Plan'}</span>
                                        <div className="text-xs text-gray-400">₹{item.price} / {item.durationDays} days</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant="success">PAID</Badge>
                                        <div className="text-xs text-gray-400">{item.paymentId}</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant={item.status === 'approved' ? 'success' : item.status === 'rejected' ? 'error' : 'warning'}>{item.status}</Badge>
                                        {item.expiryDate && <div className="text-xs text-gray-400 mt-1">Expires: {new Date(item.expiryDate).toLocaleDateString()}</div>}
                                    </td>
                                    <td className="px-6 py-4 text-right space-x-2">
                                        {activeTab === 'PENDING' && (
                                            <>
                                                <Button size="sm" variant="primary" onClick={() => handleApprove(item.id)}>Approve</Button>
                                                <Button size="sm" variant="danger" onClick={() => handleReject(item.id)}>Reject</Button>
                                            </>
                                        )}
                                        {activeTab !== 'PENDING' && item.adminNotes && <span className="text-xs text-gray-400 italic">{item.adminNotes}</span>}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            <Modal isOpen={isEditorOpen} onClose={() => setIsEditorOpen(false)} title={editingPlan.id ? 'Edit Promotion Plan' : 'Create Promotion Plan'}>
                <div className="space-y-4">
                    <Input label="Plan Name" value={editingPlan.name || ''} onChange={e => setEditingPlan({ ...editingPlan, name: e.target.value })} placeholder="e.g. 7 Day Feature" required />
                    <div className="grid grid-cols-2 gap-4">
                        <Input label="Price (₹)" type="number" value={editingPlan.price || 0} onChange={e => setEditingPlan({ ...editingPlan, price: parseInt(e.target.value) })} required />
                        <Input label="Duration (Days)" type="number" value={editingPlan.durationDays || 7} onChange={e => setEditingPlan({ ...editingPlan, durationDays: parseInt(e.target.value) })} required />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                        <textarea className="w-full border p-2 rounded-lg" rows={2} value={editingPlan.description || ''} onChange={e => setEditingPlan({ ...editingPlan, description: e.target.value })} placeholder="Benefits of this plan" />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Applicable To</label>
                            <select className="w-full border p-2 rounded-lg" value={editingPlan.applicableTo || 'both'} onChange={e => setEditingPlan({ ...editingPlan, applicableTo: e.target.value as any })}>
                                <option value="both">Both</option>
                                <option value="reading_room">Reading Rooms</option>
                                <option value="accommodation">Accommodations</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Placement</label>
                            <select className="w-full border p-2 rounded-lg" value={editingPlan.placement || 'featured_section'} onChange={e => setEditingPlan({ ...editingPlan, placement: e.target.value as any })}>
                                <option value="featured_section">Featured Section</option>
                                <option value="top_list">Top of List</option>
                                <option value="banner">Banner</option>
                            </select>
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                        <select className="w-full border p-2 rounded-lg" value={editingPlan.status || 'draft'} onChange={e => setEditingPlan({ ...editingPlan, status: e.target.value as any })}>
                            <option value="draft">Draft</option>
                            <option value="active">Active (Visible to Owners)</option>
                            <option value="inactive">Inactive</option>
                        </select>
                    </div>
                    <div className="mt-6 flex justify-end gap-3">
                        <Button variant="ghost" onClick={() => setIsEditorOpen(false)}>Cancel</Button>
                        <Button variant="primary" onClick={handleSavePlan}>Save Plan</Button>
                    </div>
                </div>
            </Modal>
        </div>
    );
};
