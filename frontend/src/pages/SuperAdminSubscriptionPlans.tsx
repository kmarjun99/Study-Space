
import React, { useState, useEffect } from 'react';
import { SubscriptionPlan } from '../types';
import { Card, Button, Input, Badge } from '../components/UI';
import { Plus, CheckCircle } from 'lucide-react';
import { subscriptionService } from '../services/subscriptionService';

export const SuperAdminSubscriptionPlans: React.FC = () => {
    const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isEditorOpen, setIsEditorOpen] = useState(false);
    const [editingPlan, setEditingPlan] = useState<Partial<SubscriptionPlan>>({
        name: '', price: 0, billingCycle: 'MONTHLY', allowedListingTypes: ['READING_ROOM'], features: [], isActive: true, isDefault: false, ctaLabel: 'Subscribe'
    });
    const [isSaving, setIsSaving] = useState(false);

    // Load plans from API on mount
    useEffect(() => {
        const loadPlans = async () => {
            setIsLoading(true);
            try {
                const apiPlans = await subscriptionService.getPlans(true); // Include inactive for Super Admin
                setPlans(apiPlans.map(p => ({
                    id: p.id,
                    name: p.name,
                    description: p.description || '',
                    price: p.price,
                    durationDays: p.durationDays,
                    features: p.features,
                    isActive: p.isActive,
                    isDefault: p.isDefault,
                    billingCycle: 'MONTHLY',
                    allowedListingTypes: ['READING_ROOM', 'ACCOMMODATION'],
                    createdAt: p.createdAt,
                    createdBy: p.createdBy || 'system',
                    ctaLabel: 'Subscribe'
                })));
            } catch (error) {
                console.error('Failed to load subscription plans:', error);
            } finally {
                setIsLoading(false);
            }
        };
        loadPlans();
    }, []);

    const handleSavePlan = async () => {
        // Validation
        if (!editingPlan.name || !editingPlan.price || editingPlan.price <= 0) {
            alert('Please enter valid name and price.');
            return;
        }

        setIsSaving(true);
        try {
            if (editingPlan.id) {
                // Update existing plan
                const updated = await subscriptionService.updatePlan(editingPlan.id, {
                    name: editingPlan.name,
                    description: editingPlan.description,
                    price: editingPlan.price,
                    duration_days: editingPlan.durationDays || 30,
                    features: editingPlan.features || [],
                    is_active: editingPlan.isActive ?? true,
                    is_default: editingPlan.isDefault ?? false
                });
                if (updated) {
                    setPlans(plans.map(p => p.id === updated.id ? {
                        ...p,
                        name: updated.name,
                        description: updated.description || '',
                        price: updated.price,
                        durationDays: updated.durationDays,
                        features: updated.features,
                        isActive: updated.isActive,
                        isDefault: updated.isDefault,
                        createdBy: updated.createdBy || p.createdBy || 'system'
                    } : p));
                    alert('Plan updated successfully!');
                }
            } else {
                // Create new plan
                const created = await subscriptionService.createPlan({
                    name: editingPlan.name || '',
                    description: editingPlan.description,
                    price: editingPlan.price || 0,
                    duration_days: editingPlan.durationDays || 30,
                    features: editingPlan.features || [],
                    is_active: editingPlan.isActive ?? true,
                    is_default: editingPlan.isDefault ?? false
                });
                if (created) {
                    setPlans([...plans, {
                        id: created.id,
                        name: created.name,
                        description: created.description || '',
                        price: created.price,
                        durationDays: created.durationDays,
                        features: created.features,
                        isActive: created.isActive,
                        isDefault: created.isDefault,
                        billingCycle: 'MONTHLY',
                        allowedListingTypes: ['READING_ROOM', 'ACCOMMODATION'],
                        createdAt: created.createdAt,
                        createdBy: created.createdBy || 'system',
                        ctaLabel: 'Subscribe'
                    }]);
                    alert('Plan created successfully!');
                }
            }

            setIsEditorOpen(false);
            setEditingPlan({ name: '', price: 0, billingCycle: 'MONTHLY', allowedListingTypes: ['READING_ROOM'], features: [], isActive: true, isDefault: false, ctaLabel: 'Subscribe' });
        } catch (error) {
            console.error('Failed to save plan:', error);
            alert('Failed to save plan. Please try again.');
        } finally {
            setIsSaving(false);
        }
    };

    const toggleFeature = (feat: string) => {
        const current = editingPlan.features || [];
        if (current.includes(feat)) {
            setEditingPlan({ ...editingPlan, features: current.filter(f => f !== feat) });
        } else {
            setEditingPlan({ ...editingPlan, features: [...current, feat] });
        }
    };

    const toggleListingType = (type: 'READING_ROOM' | 'ACCOMMODATION') => {
        const current = editingPlan.allowedListingTypes || [];
        if (current.includes(type)) {
            setEditingPlan({ ...editingPlan, allowedListingTypes: current.filter(t => t !== type) as any });
        } else {
            setEditingPlan({ ...editingPlan, allowedListingTypes: [...current, type] });
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
                <div>
                    <h2 className="text-xl sm:text-2xl font-bold text-gray-900">Subscription Plans</h2>
                    <p className="text-sm sm:text-base text-gray-500">Manage billing plans for Venue Owners.</p>
                </div>
                <Button onClick={() => { setEditingPlan({ name: '', price: 0, billingCycle: 'MONTHLY', allowedListingTypes: ['READING_ROOM'], features: [], isActive: true, isDefault: false, ctaLabel: 'Subscribe' }); setIsEditorOpen(true); }} className="w-full sm:w-auto">
                    <Plus className="w-4 h-4 mr-2" /> Create New Plan
                </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {plans.map(plan => (
                    <Card key={plan.id} className={`flex flex-col h-full border-t-4 ${plan.isActive ? 'border-t-indigo-500' : 'border-t-gray-300'}`}>
                        <div className="p-6 flex-1">
                            <div className="flex justify-between items-start mb-4">
                                <Badge variant={plan.isActive ? 'success' : 'info'}>{plan.isActive ? 'Active' : 'Inactive'}</Badge>
                                {plan.isDefault && <Badge variant="warning">Default</Badge>}
                            </div>
                            <h3 className="text-xl font-bold text-gray-900">{plan.name}</h3>
                            <p className="text-sm text-gray-500 mt-1">{plan.description}</p>
                            <div className="mt-4 flex items-baseline">
                                <span className="text-3xl font-extrabold text-gray-900">₹{plan.price}</span>
                                <span className="ml-1 text-gray-500">/{plan.billingCycle.toLowerCase()} <span className="text-xs">+ GST</span></span>
                            </div>
                            <div className="mt-6 space-y-2">
                                {plan.features.map((feat, i) => (
                                    <div key={i} className="flex items-center text-sm text-gray-600">
                                        <CheckCircle className="w-4 h-4 text-green-500 mr-2 flex-shrink-0" /> {feat}
                                    </div>
                                ))}
                                {plan.allowedListingTypes.length > 0 && (
                                    <div className="pt-2 mt-2 border-t border-gray-100 text-xs font-semibold text-gray-400 uppercase">
                                        Includes: {plan.allowedListingTypes.join(' & ')}
                                    </div>
                                )}
                            </div>
                        </div>
                        <div className="p-4 bg-gray-50 border-t border-gray-100 flex justify-between">
                            <Button size="sm" variant="outline" onClick={() => { setEditingPlan(plan); setIsEditorOpen(true); }}>Edit Plan</Button>
                        </div>
                    </Card>
                ))}
            </div>

            {isEditorOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
                    <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 shadow-2xl animate-in zoom-in-95">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-xl font-bold text-gray-900">{editingPlan.id ? 'Edit Plan' : 'Create New Plan'}</h3>
                            <Button size="sm" variant="ghost" onClick={() => setIsEditorOpen(false)}>Close</Button>
                        </div>

                        <div className="space-y-4">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <Input label="Plan Name" value={editingPlan.name || ''} onChange={e => setEditingPlan({ ...editingPlan, name: e.target.value })} required />
                                <Input label="Price (₹)" type="number" value={editingPlan.price || 0} onChange={e => setEditingPlan({ ...editingPlan, price: parseInt(e.target.value) })} required />
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Billing Cycle</label>
                                    <select className="w-full border p-2 rounded-lg" value={editingPlan.billingCycle} onChange={e => setEditingPlan({ ...editingPlan, billingCycle: e.target.value as any })}>
                                        <option value="MONTHLY">Monthly</option>
                                        <option value="QUARTERLY">Quarterly</option>
                                        <option value="YEARLY">Yearly</option>
                                    </select>
                                </div>
                                <Input label="CTA Label" value={editingPlan.ctaLabel || ''} onChange={e => setEditingPlan({ ...editingPlan, ctaLabel: e.target.value })} placeholder="e.g. Subscribe Now" />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                                <textarea className="w-full border p-2 rounded-lg" rows={2} value={editingPlan.description || ''} onChange={e => setEditingPlan({ ...editingPlan, description: e.target.value })} />
                            </div>

                            <div className="border-t border-b py-4 space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">Allowed Listing Types</label>
                                    <div className="flex gap-4">
                                        <label className="flex items-center gap-2 cursor-pointer">
                                            <input type="checkbox" checked={editingPlan.allowedListingTypes?.includes('READING_ROOM')} onChange={() => toggleListingType('READING_ROOM')} />
                                            <span>Reading Room</span>
                                        </label>
                                        <label className="flex items-center gap-2 cursor-pointer">
                                            <input type="checkbox" checked={editingPlan.allowedListingTypes?.includes('ACCOMMODATION')} onChange={() => toggleListingType('ACCOMMODATION')} />
                                            <span>PG / Hostel</span>
                                        </label>
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">Features</label>
                                    <div className="flex flex-wrap gap-2">
                                        {['Unlimited Listings', 'Basic Analytics', 'Advanced Analytics', 'Priority Support', 'Featured for 7 Days', 'API Access', 'Custom Branding'].map(feat => (
                                            <button
                                                key={feat}
                                                onClick={() => toggleFeature(feat)}
                                                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${editingPlan.features?.includes(feat) ? 'bg-indigo-100 border-indigo-200 text-indigo-700' : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'}`}
                                            >
                                                {feat}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            <div className="flex gap-6 pt-2">
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" checked={editingPlan.isActive} onChange={e => setEditingPlan({ ...editingPlan, isActive: e.target.checked })} />
                                    <span className="text-sm font-medium">Active Plan</span>
                                </label>
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input type="checkbox" checked={editingPlan.isDefault} onChange={e => setEditingPlan({ ...editingPlan, isDefault: e.target.checked })} />
                                    <span className="text-sm font-medium">Set as Default</span>
                                </label>
                            </div>
                        </div>

                        <div className="mt-6 flex justify-end gap-3">
                            <Button variant="ghost" onClick={() => setIsEditorOpen(false)}>Cancel</Button>
                            <Button variant="primary" onClick={handleSavePlan} isLoading={isSaving}>Save Plan</Button>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
};
