import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppState, User, SubscriptionPlan, ReadingRoom, Accommodation } from '../types';
import { Card, Button, Badge } from '../components/UI';
import {
    ArrowLeft, CreditCard, Check, Calendar, Receipt, Sparkles,
    TrendingUp, Clock, AlertCircle, Download, ChevronRight
} from 'lucide-react';

interface OwnerBillingProps {
    state: AppState;
    user: User;
}

export const OwnerBilling: React.FC<OwnerBillingProps> = ({ state, user }) => {
    const navigate = useNavigate();
    const [isProcessing, setIsProcessing] = useState(false);
    const [selectedUpgrade, setSelectedUpgrade] = useState<string | null>(null);

    // Guard against null user
    if (!user) {
        return (
            <div className="flex items-center justify-center h-64">
                <p className="text-gray-500">Loading...</p>
            </div>
        );
    }

    // Find owner's venue(s)
    const myVenue = state.readingRooms?.find(r => r.ownerId === user.id);
    const myAccommodation = state.accommodations?.find(a => a.ownerId === user.id);

    // Get current plan (mock - in real app, would be linked to venue subscription)
    const currentPlan = useMemo(() => {
        // For demo, assume "Standard" plan if venue exists
        const plans = state.subscriptionPlans || [];
        return plans.find(p => p.isDefault) || plans[0] || null;
    }, [state.subscriptionPlans]);

    // Mock billing data
    const billingData = useMemo(() => {
        const startDate = new Date();
        startDate.setMonth(startDate.getMonth() - 1);
        const renewalDate = new Date();
        renewalDate.setMonth(renewalDate.getMonth() + 1);

        // Derive billing cycle from duration days
        const getBillingCycle = (days?: number) => {
            if (!days) return 'MONTHLY';
            if (days <= 30) return 'MONTHLY';
            if (days <= 90) return 'QUARTERLY';
            return 'YEARLY';
        };

        return {
            planStartDate: startDate.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }),
            renewalDate: renewalDate.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }),
            billingCycle: getBillingCycle(currentPlan?.durationDays),
            status: 'ACTIVE' as const,
            invoices: [
                { id: 'INV-001', date: startDate.toLocaleDateString(), amount: currentPlan?.price || 999, status: 'PAID' },
                { id: 'INV-002', date: new Date(startDate.getTime() - 30 * 24 * 60 * 60 * 1000).toLocaleDateString(), amount: currentPlan?.price || 999, status: 'PAID' },
            ]
        };
    }, [currentPlan]);

    const handleUpgrade = (planId: string) => {
        setSelectedUpgrade(planId);
        setIsProcessing(true);
        // Mock payment
        setTimeout(() => {
            setIsProcessing(false);
            setSelectedUpgrade(null);
            alert('Plan upgraded successfully! (Demo)');
        }, 2000);
    };

    const upgradePlans = (state.subscriptionPlans || []).filter(p => !p.isDefault && p.price > (currentPlan?.price || 0));

    return (
        <div className="max-w-4xl mx-auto pb-10">
            {/* Header */}
            <div className="mb-6">
                <button
                    onClick={() => navigate('/admin/profile')}
                    className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4 mr-1" /> Back to Profile
                </button>
                <h1 className="text-2xl font-bold text-gray-900">Subscription & Billing</h1>
                <p className="text-gray-500 mt-1">Manage your plan, billing cycle, and payment history</p>
            </div>

            {/* Current Plan Card */}
            <Card className="p-6 mb-6 bg-gradient-to-br from-indigo-50 to-white border-indigo-100">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    <div>
                        <div className="flex items-center gap-2 mb-2">
                            <CreditCard className="w-5 h-5 text-indigo-600" />
                            <span className="text-sm font-medium text-indigo-600 uppercase tracking-wide">Current Plan</span>
                        </div>
                        <h2 className="text-2xl font-bold text-gray-900 mb-1">{currentPlan?.name || 'Standard Listing'}</h2>
                        <p className="text-gray-600 text-sm">{currentPlan?.description || 'Manage your reading room with basic features'}</p>
                    </div>
                    <div className="text-right">
                        <div className="text-3xl font-bold text-indigo-600">
                            ₹{currentPlan?.price || 999}
                            <span className="text-sm font-normal text-gray-500">/{billingData.billingCycle.toLowerCase()}</span>
                        </div>
                        <Badge variant="success" className="mt-2">
                            <Check className="w-3 h-3 mr-1" /> {billingData.status}
                        </Badge>
                    </div>
                </div>

                {/* Plan Features */}
                <div className="mt-6 pt-4 border-t border-indigo-100">
                    <h4 className="text-sm font-medium text-gray-700 mb-3">Plan Features</h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {(currentPlan?.features || ['Unlimited Cabins', 'Student Dashboard', 'Basic Analytics']).map((feature, i) => (
                            <div key={i} className="flex items-center gap-2 text-sm text-gray-600">
                                <Check className="w-4 h-4 text-green-500" />
                                <span>{feature}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </Card>

            {/* Billing Info */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <Card className="p-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-50 rounded-lg">
                            <Calendar className="w-5 h-5 text-blue-600" />
                        </div>
                        <div>
                            <p className="text-xs text-gray-500">Next Renewal</p>
                            <p className="font-semibold text-gray-900">{billingData.renewalDate}</p>
                        </div>
                    </div>
                </Card>
                <Card className="p-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-green-50 rounded-lg">
                            <Clock className="w-5 h-5 text-green-600" />
                        </div>
                        <div>
                            <p className="text-xs text-gray-500">Billing Cycle</p>
                            <p className="font-semibold text-gray-900 capitalize">{billingData.billingCycle.toLowerCase()}</p>
                        </div>
                    </div>
                </Card>
                <Card className="p-4">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-purple-50 rounded-lg">
                            <Receipt className="w-5 h-5 text-purple-600" />
                        </div>
                        <div>
                            <p className="text-xs text-gray-500">Started On</p>
                            <p className="font-semibold text-gray-900">{billingData.planStartDate}</p>
                        </div>
                    </div>
                </Card>
            </div>

            {/* Upgrade Options */}
            {upgradePlans.length > 0 && (
                <Card className="p-6 mb-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Sparkles className="w-5 h-5 text-yellow-500" />
                        <h3 className="text-lg font-bold text-gray-900">Upgrade Your Plan</h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {upgradePlans.map(plan => (
                            <div
                                key={plan.id}
                                className="p-4 border rounded-xl hover:border-indigo-300 hover:bg-indigo-50/50 transition-colors"
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <div>
                                        <h4 className="font-bold text-gray-900">{plan.name}</h4>
                                        <p className="text-sm text-gray-500">{plan.description}</p>
                                    </div>
                                    <span className="text-lg font-bold text-indigo-600">₹{plan.price}<span className="text-xs text-gray-500"> + GST</span></span>
                                </div>
                                <Button
                                    size="sm"
                                    className="w-full mt-3"
                                    onClick={() => handleUpgrade(plan.id)}
                                    isLoading={isProcessing && selectedUpgrade === plan.id}
                                >
                                    <TrendingUp className="w-4 h-4 mr-2" /> Upgrade
                                </Button>
                            </div>
                        ))}
                    </div>
                </Card>
            )}

            {/* Featured Listing Boost */}
            {(myVenue || myAccommodation) && (
                <Card className="p-6 mb-6 bg-gradient-to-r from-yellow-50 to-orange-50 border-yellow-200">
                    <div className="flex items-start gap-4">
                        <div className="p-3 bg-yellow-100 rounded-xl">
                            <Sparkles className="w-6 h-6 text-yellow-600" />
                        </div>
                        <div className="flex-1">
                            <h3 className="font-bold text-gray-900 mb-1">Boost Your Visibility</h3>
                            <p className="text-sm text-gray-600 mb-3">
                                Get featured in top listings and increase your bookings by up to 5x
                            </p>
                            <Button
                                variant="outline"
                                className="border-yellow-400 text-yellow-700 hover:bg-yellow-100"
                                onClick={() => navigate('/admin/venue')}
                            >
                                Manage Featured Listing <ChevronRight className="w-4 h-4 ml-1" />
                            </Button>
                        </div>
                    </div>
                </Card>
            )}

            {/* Payment History */}
            <Card className="p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">Payment History</h3>
                <div className="overflow-hidden rounded-lg border">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Invoice</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Amount</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase"></th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {billingData.invoices.map(inv => (
                                <tr key={inv.id}>
                                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{inv.id}</td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{inv.date}</td>
                                    <td className="px-4 py-3 text-sm font-medium text-gray-900">₹{inv.amount}</td>
                                    <td className="px-4 py-3">
                                        <Badge variant={inv.status === 'PAID' ? 'success' : 'warning'} className="text-xs">
                                            {inv.status}
                                        </Badge>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <button className="text-indigo-600 hover:text-indigo-800 text-sm font-medium">
                                            <Download className="w-4 h-4" />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {billingData.invoices.length === 0 && (
                    <div className="text-center py-8 text-gray-400">
                        <Receipt className="w-12 h-12 mx-auto mb-2 opacity-30" />
                        <p>No invoices yet</p>
                    </div>
                )}
            </Card>
        </div>
    );
};

export default OwnerBilling;
