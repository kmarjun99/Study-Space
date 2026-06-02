/**
 * Owner KYC submission page.
 *
 * This is the piece that was completely missing: the super-admin had a
 * KYC review queue but owners had no way to submit their details. Without
 * this, kyc_status stayed unset, the review queue was empty, and listings
 * could never pass the `assert_owner_kyc_verified` gate to go LIVE.
 *
 * Flow:
 *   - On mount, GET /api/owner/kyc to prefill any existing data + show the
 *     current status (PENDING / VERIFIED / REJECTED / unset).
 *   - If REJECTED or re-upload requested, the reviewer's note is shown so
 *     the owner knows what to fix.
 *   - On submit, PUT /api/owner/kyc → status becomes PENDING for review.
 *   - If already VERIFIED, the form is locked (backend 409s anyway) with
 *     a "contact support to change" message.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Input, Badge } from '../components/UI';
import {
    ArrowLeft, ShieldCheck, AlertCircle, CheckCircle2, Clock, XCircle,
} from 'lucide-react';
import {
    ownerKycService, OwnerKYCMine, OwnerKYCSubmit, KYCStatus, GSTRegType,
} from '../services/kycService';

// Indian state codes for the business-state dropdown. Two-letter GST state
// codes — must match what the platform.home_state config + place-of-supply
// logic expect.
const STATE_CODES: { code: string; name: string }[] = [
    { code: 'AN', name: 'Andaman & Nicobar' }, { code: 'AP', name: 'Andhra Pradesh' },
    { code: 'AR', name: 'Arunachal Pradesh' }, { code: 'AS', name: 'Assam' },
    { code: 'BR', name: 'Bihar' }, { code: 'CH', name: 'Chandigarh' },
    { code: 'CT', name: 'Chhattisgarh' }, { code: 'DL', name: 'Delhi' },
    { code: 'GA', name: 'Goa' }, { code: 'GJ', name: 'Gujarat' },
    { code: 'HR', name: 'Haryana' }, { code: 'HP', name: 'Himachal Pradesh' },
    { code: 'JK', name: 'Jammu & Kashmir' }, { code: 'JH', name: 'Jharkhand' },
    { code: 'KA', name: 'Karnataka' }, { code: 'KL', name: 'Kerala' },
    { code: 'LA', name: 'Ladakh' }, { code: 'LD', name: 'Lakshadweep' },
    { code: 'MP', name: 'Madhya Pradesh' }, { code: 'MH', name: 'Maharashtra' },
    { code: 'MN', name: 'Manipur' }, { code: 'ML', name: 'Meghalaya' },
    { code: 'MZ', name: 'Mizoram' }, { code: 'NL', name: 'Nagaland' },
    { code: 'OR', name: 'Odisha' }, { code: 'PY', name: 'Puducherry' },
    { code: 'PB', name: 'Punjab' }, { code: 'RJ', name: 'Rajasthan' },
    { code: 'SK', name: 'Sikkim' }, { code: 'TN', name: 'Tamil Nadu' },
    { code: 'TG', name: 'Telangana' }, { code: 'TR', name: 'Tripura' },
    { code: 'UP', name: 'Uttar Pradesh' }, { code: 'UT', name: 'Uttarakhand' },
    { code: 'WB', name: 'West Bengal' },
];

const REG_TYPES: { value: GSTRegType; label: string }[] = [
    { value: 'REGULAR', label: 'Regular (has GSTIN)' },
    { value: 'COMPOSITION', label: 'Composition scheme (has GSTIN)' },
    { value: 'UNREGISTERED', label: 'Unregistered (no GSTIN)' },
];

const statusMeta = (s: KYCStatus | null) => {
    switch (s) {
        case 'VERIFIED':
            return { variant: 'success' as const, icon: CheckCircle2, label: 'Verified' };
        case 'PENDING':
            return { variant: 'warning' as const, icon: Clock, label: 'Under review' };
        case 'REJECTED':
            return { variant: 'error' as const, icon: XCircle, label: 'Rejected' };
        default:
            return { variant: 'info' as const, icon: AlertCircle, label: 'Not submitted' };
    }
};

interface OwnerKYCProps {
    // present for parity with other owner pages; not strictly needed
    user?: { id: string; name: string };
}

export const OwnerKYC: React.FC<OwnerKYCProps> = () => {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [record, setRecord] = useState<OwnerKYCMine | null>(null);

    const [form, setForm] = useState<OwnerKYCSubmit>({
        legal_name: '',
        gst_registration_type: 'UNREGISTERED',
        business_state_code: '',
        pan: '',
        gstin: '',
        bank_account_holder: '',
        bank_account_number: '',
        bank_ifsc: '',
    });

    useEffect(() => {
        (async () => {
            try {
                const data = await ownerKycService.getMine();
                setRecord(data);
                setForm(f => ({
                    ...f,
                    legal_name: data.legal_name || '',
                    gst_registration_type: data.gst_registration_type || 'UNREGISTERED',
                    business_state_code: data.business_state_code || '',
                    pan: data.pan || '',
                    gstin: data.gstin || '',
                    bank_account_holder: data.bank_account_holder || '',
                    // Never prefill the account number — backend only returns the
                    // masked value. The owner re-enters it on each submission.
                    bank_account_number: '',
                    bank_ifsc: data.bank_ifsc || '',
                }));
            } catch (e: any) {
                setError(e?.response?.data?.detail || 'Could not load your KYC record.');
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    const isVerified = record?.kyc_status === 'VERIFIED';
    const meta = statusMeta(record?.kyc_status ?? null);
    const StatusIcon = meta.icon;
    const needsGstin = form.gst_registration_type !== 'UNREGISTERED';

    const set = (k: keyof OwnerKYCSubmit) =>
        (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
            setForm(prev => ({ ...prev, [k]: e.target.value }));

    const canSubmit = useMemo(() => {
        if (isVerified) return false;
        if (!form.legal_name.trim()) return false;
        if (!form.business_state_code) return false;
        if (!form.pan?.trim()) return false;
        if (needsGstin && !form.gstin?.trim()) return false;
        if (!form.bank_account_holder.trim()) return false;
        if (!form.bank_account_number.trim()) return false;
        if (!form.bank_ifsc.trim()) return false;
        return true;
    }, [form, needsGstin, isVerified]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError(null);
        setSuccess(false);
        try {
            const updated = await ownerKycService.submitMine({
                ...form,
                pan: form.pan?.trim().toUpperCase() || null,
                gstin: needsGstin ? (form.gstin?.trim().toUpperCase() || null) : null,
                business_state_code: form.business_state_code.toUpperCase(),
                bank_ifsc: form.bank_ifsc.trim().toUpperCase(),
            });
            setRecord(updated);
            setSuccess(true);
        } catch (e: any) {
            // Pydantic validation errors arrive as an array of {msg}.
            const detail = e?.response?.data?.detail;
            if (Array.isArray(detail)) {
                setError(detail.map((d: any) => d.msg).join('; '));
            } else {
                setError(detail || 'Could not submit KYC. Please check your details.');
            }
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="max-w-2xl mx-auto p-6 text-gray-500">Loading your KYC…</div>
        );
    }

    return (
        <div className="max-w-2xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>

            <div className="flex items-center gap-3 mb-1">
                <ShieldCheck className="w-7 h-7 text-indigo-600" />
                <h1 className="text-2xl font-bold text-gray-900">Owner KYC</h1>
                <Badge variant={meta.variant} className="ml-1 flex items-center gap-1">
                    <StatusIcon className="w-3 h-3" /> {meta.label}
                </Badge>
            </div>
            <p className="text-gray-500 text-sm mb-6">
                Your listings can only go live after KYC is verified. Submit your
                legal + bank details below; our team reviews within 1–2 business days.
            </p>

            {/* Reviewer feedback — shown when rejected / re-upload requested. */}
            {record?.kyc_notes && record.kyc_status !== 'VERIFIED' && (
                <Card className="p-4 mb-6 border-amber-200 bg-amber-50">
                    <div className="flex items-start gap-2 text-sm text-amber-900">
                        <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <div>
                            <strong>Reviewer note:</strong> {record.kyc_notes}
                        </div>
                    </div>
                </Card>
            )}

            {isVerified && (
                <Card className="p-4 mb-6 border-emerald-200 bg-emerald-50">
                    <div className="flex items-start gap-2 text-sm text-emerald-900">
                        <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <div>
                            Your KYC is verified. To change any verified detail (bank
                            account, GSTIN, etc.) please contact support — changes need
                            re-verification.
                        </div>
                    </div>
                </Card>
            )}

            {success && (
                <Card className="p-4 mb-6 border-indigo-200 bg-indigo-50">
                    <div className="flex items-start gap-2 text-sm text-indigo-900">
                        <Clock className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <div>
                            KYC submitted. Status is now <strong>Under review</strong>.
                            You'll be notified once it's verified.
                        </div>
                    </div>
                </Card>
            )}

            {error && (
                <Card className="p-4 mb-6 border-red-200 bg-red-50 text-sm text-red-700">{error}</Card>
            )}

            <form onSubmit={handleSubmit}>
                <Card className="p-6 mb-4">
                    <h2 className="text-base font-bold text-gray-900 mb-4">Legal & tax</h2>
                    <div className="space-y-4">
                        <Input
                            label="Legal name (as on PAN)"
                            value={form.legal_name}
                            onChange={set('legal_name')}
                            placeholder="e.g. Kumar Reading Spaces Pvt Ltd"
                            disabled={isVerified}
                        />
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                GST registration type
                            </label>
                            <select
                                value={form.gst_registration_type}
                                onChange={set('gst_registration_type')}
                                disabled={isVerified}
                                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
                            >
                                {REG_TYPES.map(r => (
                                    <option key={r.value} value={r.value}>{r.label}</option>
                                ))}
                            </select>
                        </div>
                        <Input
                            label="PAN"
                            value={form.pan ?? ''}
                            onChange={set('pan')}
                            placeholder="ABCDE1234F"
                            disabled={isVerified}
                            maxLength={10}
                            style={{ textTransform: 'uppercase' }}
                        />
                        {needsGstin && (
                            <Input
                                label="GSTIN"
                                value={form.gstin ?? ''}
                                onChange={set('gstin')}
                                placeholder="29ABCDE1234F1Z5"
                                disabled={isVerified}
                                maxLength={15}
                                style={{ textTransform: 'uppercase' }}
                            />
                        )}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Business state
                            </label>
                            <select
                                value={form.business_state_code}
                                onChange={set('business_state_code')}
                                disabled={isVerified}
                                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
                            >
                                <option value="">Select state…</option>
                                {STATE_CODES.map(s => (
                                    <option key={s.code} value={s.code}>{s.name} ({s.code})</option>
                                ))}
                            </select>
                        </div>
                    </div>
                </Card>

                <Card className="p-6 mb-6">
                    <h2 className="text-base font-bold text-gray-900 mb-1">Bank account for payouts</h2>
                    <p className="text-xs text-gray-500 mb-4">
                        Booking revenue (net of platform fee + GST) is settled to this
                        account. Re-enter the full account number each time you submit —
                        we only ever show you the last 4 digits afterward.
                    </p>
                    <div className="space-y-4">
                        <Input
                            label="Account holder name"
                            value={form.bank_account_holder}
                            onChange={set('bank_account_holder')}
                            disabled={isVerified}
                        />
                        <Input
                            label={record?.bank_account_number_masked
                                ? `Account number (current: ${record.bank_account_number_masked})`
                                : 'Account number'}
                            value={form.bank_account_number}
                            onChange={set('bank_account_number')}
                            placeholder="Re-enter full account number"
                            disabled={isVerified}
                        />
                        <Input
                            label="IFSC"
                            value={form.bank_ifsc}
                            onChange={set('bank_ifsc')}
                            placeholder="HDFC0001234"
                            disabled={isVerified}
                            maxLength={11}
                            style={{ textTransform: 'uppercase' }}
                        />
                    </div>
                </Card>

                {!isVerified && (
                    <Button type="submit" isLoading={saving} disabled={!canSubmit}>
                        {record?.kyc_status === 'PENDING' ? 'Update & resubmit' : 'Submit for verification'}
                    </Button>
                )}
            </form>
        </div>
    );
};

export default OwnerKYC;
