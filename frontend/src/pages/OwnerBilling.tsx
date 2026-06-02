import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppState, User, SubscriptionPlan, ReadingRoom, Accommodation } from '../types';
import { Card, Button, Badge } from '../components/UI';
import {
    ArrowLeft, CreditCard, Check, Calendar, Receipt, Sparkles,
    TrendingUp, Clock, AlertCircle, Download, ChevronRight
} from 'lucide-react';
import { ownerBillingService, OwnerCharge } from '../services/ownerBillingService';

interface OwnerBillingProps {
    state: AppState;
    user: User;
}

export const OwnerBilling: React.FC<OwnerBillingProps> = ({ state, user }) => {
    const navigate = useNavigate();
    const [isProcessing, setIsProcessing] = useState(false);
    const [selectedUpgrade, setSelectedUpgrade] = useState<string | null>(null);

    // ---- Real platform charges from the new accounting API ----
    const [charges, setCharges] = useState<OwnerCharge[]>([]);
    const [chargesLoading, setChargesLoading] = useState(false);
    const [chargesError, setChargesError] = useState<string | null>(null);
    const [payingChargeId, setPayingChargeId] = useState<string | null>(null);

    const refreshCharges = useCallback(async () => {
        setChargesLoading(true);
        setChargesError(null);
        try {
            const rows = await ownerBillingService.listCharges();
            setCharges(rows);
        } catch (e: any) {
            // Endpoint may be unmounted in older deployments — fail soft, hide section.
            setChargesError(e?.response?.status === 404 ? null : 'Could not load platform charges.');
            setCharges([]);
        } finally {
            setChargesLoading(false);
        }
    }, []);

    useEffect(() => {
        if (user) {
            void refreshCharges();
        }
    }, [user, refreshCharges]);

    const handlePayCharge = async (chargeId: string) => {
        setPayingChargeId(chargeId);
        try {
            const order = await ownerBillingService.createPayOrder(chargeId);
            // Reuse the global Razorpay (loaded by existing RazorpayPayment component).
            const w = window as any;
            if (!w.Razorpay || order.is_demo) {
                // Demo / no SDK loaded — confirm directly via API for parity with existing flow.
                const demoPaymentId = `pay_demo_${Date.now()}`;
                await ownerBillingService.confirmPayment(chargeId, demoPaymentId);
                await refreshCharges();
                return;
            }
            const rzp = new w.Razorpay({
                key: order.razorpay_key_id,
                amount: order.amount,
                currency: order.currency,
                order_id: order.order_id,
                name: 'mySpace',
                description: 'Platform charge',
                handler: async (resp: any) => {
                    try {
                        await ownerBillingService.confirmPayment(chargeId, resp.razorpay_payment_id);
                    } finally {
                        await refreshCharges();
                    }
                },
                modal: { ondismiss: () => setPayingChargeId(null) },
            });
            rzp.open();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not start payment.');
        } finally {
            setPayingChargeId(null);
        }
    };

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

    // The plan is "active" ONLY when there is a PAID LISTING_FEE charge.
    // Previously this page picked the default plan from the catalogue and
    // hardcoded status:'ACTIVE' — so a brand-new owner who never paid saw
    // a live plan. The real source of truth is owner_charges: a paid
    // LISTING_FEE means the listing subscription is active.
    const paidListingFee = useMemo(
        () => charges
            .filter(c => c.charge_type === 'LISTING_FEE' && c.status === 'PAID')
            .sort((a, b) => new Date(b.paid_at || b.created_at).getTime()
                - new Date(a.paid_at || a.created_at).getTime())[0] || null,
        [charges],
    );
    const duePlanCharge = useMemo(
        () => charges.find(c => c.charge_type === 'LISTING_FEE'
            && (c.status === 'DUE' || c.status === 'OVERDUE' || c.status === 'FAILED')) || null,
        [charges],
    );
    const hasActivePlan = !!paidListingFee;

    // The catalogue plan is only used to show feature bullets + price, NOT to
    // imply the owner is subscribed. Real subscription state = paidListingFee.
    const currentPlan = useMemo(() => {
        const plans = state.subscriptionPlans || [];
        return plans.find(p => p.isDefault) || plans[0] || null;
    }, [state.subscriptionPlans]);

    // Plan summary header — dates derived from the REAL paid listing-fee
    // charge, not a fabricated "one month ago" window.
    const billingData = useMemo(() => {
        const getBillingCycle = (days?: number) => {
            if (!days) return 'MONTHLY';
            if (days <= 30) return 'MONTHLY';
            if (days <= 90) return 'QUARTERLY';
            return 'YEARLY';
        };
        const fmt = (d: Date) => d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

        if (!paidListingFee) {
            return {
                planStartDate: '—',
                renewalDate: '—',
                billingCycle: getBillingCycle(currentPlan?.durationDays),
                status: 'NOT_ACTIVE' as const,
            };
        }
        const start = new Date(paidListingFee.paid_at || paidListingFee.created_at);
        const renewal = new Date(start);
        renewal.setDate(renewal.getDate() + (currentPlan?.durationDays || 30));
        return {
            planStartDate: fmt(start),
            renewalDate: fmt(renewal),
            billingCycle: getBillingCycle(currentPlan?.durationDays),
            status: 'ACTIVE' as const,
        };
    }, [paidListingFee, currentPlan]);

    // Real payment-history rows: PAID owner_charges that have an issued
    // invoice. Sorted newest-first by paid_at (falls back to created_at).
    const paidInvoiceCharges = useMemo(() => {
        return charges
            .filter(c => c.status === 'PAID' && c.invoice_id)
            .sort((a, b) => {
                const ta = new Date(a.paid_at || a.created_at).getTime();
                const tb = new Date(b.paid_at || b.created_at).getTime();
                return tb - ta;
            });
    }, [charges]);

    const [downloadingChargeId, setDownloadingChargeId] = useState<string | null>(null);
    const handleDownloadInvoice = async (chargeId: string) => {
        setDownloadingChargeId(chargeId);
        try {
            await ownerBillingService.downloadInvoicePdf(chargeId);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not download invoice. Please try again.');
        } finally {
            setDownloadingChargeId(null);
        }
    };

    // Plan upgrades route through the real listing-fee charge + Razorpay
    // flow, not a fake setTimeout. We create (or reuse) a LISTING_FEE charge
    // for the chosen plan, then open the pay flow. This reuses the same
    // handlePayCharge path the DUE charges below use.
    const handleUpgrade = async (planId: string) => {
        const myListingId = myVenue?.id || myAccommodation?.id;
        const listingType: 'READING_ROOM' | 'ACCOMMODATION' | null =
            myVenue ? 'READING_ROOM' : (myAccommodation ? 'ACCOMMODATION' : null);
        if (!myListingId || !listingType) {
            alert('Create a listing first, then choose a plan for it.');
            return;
        }
        setSelectedUpgrade(planId);
        setIsProcessing(true);
        try {
            const charge = await ownerBillingService.createListingFee({
                listing_id: myListingId,
                listing_type: listingType,
                plan_id: planId,
            });
            await refreshCharges();
            // Immediately kick off payment for the freshly-created charge.
            await handlePayCharge(charge.id);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not start the plan payment. Please try again.');
        } finally {
            setIsProcessing(false);
            setSelectedUpgrade(null);
        }
    };

    // When the owner has NO active plan, show every plan so they can pick
    // one (including the base/default plan). When they DO have an active
    // plan, show only higher-priced plans as upgrade options.
    const selectablePlans = useMemo(() => {
        const plans = state.subscriptionPlans || [];
        if (!hasActivePlan) return plans;
        return plans.filter(p => !p.isDefault && p.price > (currentPlan?.price || 0));
    }, [state.subscriptionPlans, hasActivePlan, currentPlan]);

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

            {/* Current Plan Card — only shows an ACTIVE plan when a
                LISTING_FEE charge has actually been PAID. */}
            {hasActivePlan ? (
                <Card className="p-6 mb-6 bg-gradient-to-br from-indigo-50 to-white border-indigo-100">
                    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                        <div>
                            <div className="flex items-center gap-2 mb-2">
                                <CreditCard className="w-5 h-5 text-indigo-600" />
                                <span className="text-sm font-medium text-indigo-600 uppercase tracking-wide">Current Plan</span>
                            </div>
                            <h2 className="text-2xl font-bold text-gray-900 mb-1">{currentPlan?.name || 'Listing Plan'}</h2>
                            <p className="text-gray-600 text-sm">{currentPlan?.description || 'Active listing subscription'}</p>
                        </div>
                        <div className="text-right">
                            <div className="text-3xl font-bold text-indigo-600">
                                ₹{paidListingFee?.total_amount ?? currentPlan?.price ?? 0}
                            </div>
                            <Badge variant="success" className="mt-2">
                                <Check className="w-3 h-3 mr-1" /> ACTIVE
                            </Badge>
                        </div>
                    </div>
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
            ) : (
                <Card className="p-6 mb-6 border-amber-200 bg-amber-50">
                    <div className="flex items-start gap-3">
                        <AlertCircle className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                            <h2 className="text-lg font-bold text-gray-900 mb-1">No active plan</h2>
                            <p className="text-sm text-gray-600 mb-3">
                                {duePlanCharge
                                    ? 'Your listing fee is pending payment. Pay it below to activate your listing — until then your venue cannot go live.'
                                    : 'You don’t have an active listing subscription yet. Choose a plan below to list your venue. Your listing stays in draft until the listing fee is paid.'}
                            </p>
                            {duePlanCharge && (
                                <Button
                                    size="sm"
                                    onClick={() => handlePayCharge(duePlanCharge.id)}
                                    isLoading={payingChargeId === duePlanCharge.id}
                                >
                                    <CreditCard className="w-4 h-4 mr-1" /> Pay ₹{duePlanCharge.total_amount} listing fee
                                </Button>
                            )}
                        </div>
                    </div>
                </Card>
            )}

            {/* Billing Info — only meaningful when a plan is active. */}
            {hasActivePlan && (
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
            )}

            {/* Plan selection — "Choose a Plan" for new owners, "Upgrade" for
                owners who already have an active plan. */}
            {selectablePlans.length > 0 && (
                <Card className="p-6 mb-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Sparkles className="w-5 h-5 text-yellow-500" />
                        <h3 className="text-lg font-bold text-gray-900">
                            {hasActivePlan ? 'Upgrade Your Plan' : 'Choose a Plan'}
                        </h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {selectablePlans.map(plan => (
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
                                    <TrendingUp className="w-4 h-4 mr-2" />
                                    {hasActivePlan ? 'Upgrade' : 'Choose & Pay'}
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

            {/* ---- Platform Charges (new accounting layer) ---- */}
            {(charges.length > 0 || chargesError) && (
                <Card className="p-6 mb-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-bold text-gray-900">Platform Charges</h3>
                        <span className="text-xs text-gray-500">
                            Listing fee &amp; monthly maintenance — incl. GST
                        </span>
                    </div>
                    {chargesError && (
                        <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700 mb-3">
                            <AlertCircle className="w-4 h-4 inline mr-1" /> {chargesError}
                        </div>
                    )}
                    {chargesLoading ? (
                        <div className="text-sm text-gray-500">Loading charges…</div>
                    ) : (
                        <div className="overflow-hidden rounded-lg border">
                            <table className="min-w-full divide-y divide-gray-200">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Period</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Base</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">GST</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Total</th>
                                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Action</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {charges.map(c => {
                                        const isPaid = c.status === 'PAID';
                                        const isOverdue = c.status === 'OVERDUE' || c.status === 'FAILED';
                                        return (
                                            <tr key={c.id}>
                                                <td className="px-4 py-3 text-sm font-medium text-gray-900">
                                                    {c.charge_type.replace('_', ' ')}
                                                </td>
                                                <td className="px-4 py-3 text-sm text-gray-500">{c.period_key || 'One-time'}</td>
                                                <td className="px-4 py-3 text-sm text-right text-gray-700">₹{c.base_amount.toFixed(2)}</td>
                                                <td className="px-4 py-3 text-sm text-right text-gray-700">₹{c.gst_amount.toFixed(2)}</td>
                                                <td className="px-4 py-3 text-sm text-right font-semibold text-gray-900">₹{c.total_amount.toFixed(2)}</td>
                                                <td className="px-4 py-3">
                                                    <Badge variant={isPaid ? 'success' : isOverdue ? 'error' : 'warning'} className="text-xs">
                                                        {c.status}
                                                    </Badge>
                                                </td>
                                                <td className="px-4 py-3 text-right">
                                                    {!isPaid && c.status !== 'WAIVED' && (
                                                        <Button
                                                            size="sm"
                                                            onClick={() => handlePayCharge(c.id)}
                                                            isLoading={payingChargeId === c.id}
                                                        >
                                                            Pay Now
                                                        </Button>
                                                    )}
                                                    {isPaid && c.invoice_id && (
                                                        <span className="text-xs text-gray-500">Invoice issued</span>
                                                    )}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
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
                            {paidInvoiceCharges.map(c => {
                                const dateStr = new Date(c.paid_at || c.created_at)
                                    .toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
                                const isDownloading = downloadingChargeId === c.id;
                                return (
                                    <tr key={c.id}>
                                        <td className="px-4 py-3 text-sm font-medium text-gray-900">
                                            {c.charge_type.replace('_', ' ')}
                                            {c.period_key ? ` · ${c.period_key}` : ''}
                                        </td>
                                        <td className="px-4 py-3 text-sm text-gray-500">{dateStr}</td>
                                        <td className="px-4 py-3 text-sm font-medium text-gray-900">₹{c.total_amount.toFixed(2)}</td>
                                        <td className="px-4 py-3">
                                            <Badge variant="success" className="text-xs">PAID</Badge>
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <button
                                                type="button"
                                                onClick={() => handleDownloadInvoice(c.id)}
                                                disabled={isDownloading}
                                                title="Download invoice (PDF)"
                                                aria-label={`Download invoice for ${c.charge_type.replace('_', ' ')}`}
                                                className="text-indigo-600 hover:text-indigo-800 text-sm font-medium disabled:opacity-50"
                                            >
                                                <Download className={`w-4 h-4 ${isDownloading ? 'animate-pulse' : ''}`} />
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
                {paidInvoiceCharges.length === 0 && (
                    <div className="text-center py-8 text-gray-400">
                        <Receipt className="w-12 h-12 mx-auto mb-2 opacity-30" />
                        <p>No invoices yet</p>
                        <p className="text-xs mt-1">Paid platform charges will appear here with a downloadable invoice.</p>
                    </div>
                )}
            </Card>
        </div>
    );
};

export default OwnerBilling;
