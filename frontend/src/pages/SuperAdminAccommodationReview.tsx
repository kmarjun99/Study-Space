
// pages/SuperAdminAccommodationReview.tsx

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Accommodation, ListingStatus, User } from '../types';
import { supplyService } from '../services/supplyService';
import { userService } from '../services/userService';
import { Card, Button, Badge } from '../components/UI';
import { MapPin, User as UserIcon, Phone, Mail, Building2, CheckCircle, XCircle, Grid, ArrowLeft, AlertTriangle, Shield, Home, ExternalLink, Flag } from 'lucide-react';

export const SuperAdminAccommodationReview = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [accommodation, setAccommodation] = useState<Accommodation | null>(null);
    const [owner, setOwner] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Safety Checks
    const [hasReviewedImages, setHasReviewedImages] = useState(false);
    const [hasVerifiedAddress, setHasVerifiedAddress] = useState(false);

    // Actions
    const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
    const [rejectionReason, setRejectionReason] = useState('');
    const [isProcessing, setIsProcessing] = useState(false);

    useEffect(() => {
        if (id) fetchAccommodation(id);
    }, [id]);

    const fetchAccommodation = async (accId: string) => {
        setLoading(true);
        try {
            const response = await supplyService.getAllAccommodations(true);
            const acc = response.find(a => a.id === accId);
            if (acc) {
                setAccommodation(acc);
                // Fetch owner details
                if (acc.ownerId) {
                    const ownerData = await userService.getUserById(acc.ownerId);
                    setOwner(ownerData);
                }
            } else {
                setError('Accommodation not found.');
            }
        } catch (err) {
            setError('Failed to load accommodation details.');
        } finally {
            setLoading(false);
        }
    };

    const handleVerify = async () => {
        if (!accommodation) return;
        if (!confirm('Are you sure you want to verify this listing? It will become visible to users immediately.')) return;

        setIsProcessing(true);
        try {
            await supplyService.verifyEntity(accommodation.id, 'accommodation');
            alert('Accommodation verified successfully!');
            navigate('/super-admin/supply');
        } catch (err) {
            alert('Failed to verify.');
        } finally {
            setIsProcessing(false);
        }
    };

    const handleReject = async () => {
        if (!accommodation || !rejectionReason.trim()) return;

        setIsProcessing(true);
        try {
            await supplyService.rejectEntity(accommodation.id, 'accommodation', rejectionReason);
            alert('Accommodation rejected and owner notified.');
            setIsRejectModalOpen(false);
            navigate('/super-admin/supply');
        } catch (err) {
            alert('Failed to reject.');
        } finally {
            setIsProcessing(false);
        }
    };

    if (loading) return <div className="p-10 text-center text-gray-500">Loading details...</div>;
    if (error || !accommodation) return <div className="p-10 text-center text-red-500">{error || 'Accommodation not found'}</div>;

    // Parse images
    let images: string[] = [];
    try {
        if (accommodation.images) {
            const parsed = JSON.parse(accommodation.images);
            if (Array.isArray(parsed)) images = parsed;
        } else if (accommodation.imageUrl) {
            images = [accommodation.imageUrl];
        }
    } catch {
        if (accommodation.imageUrl) images = [accommodation.imageUrl];
    }

    const canVerify = hasReviewedImages && hasVerifiedAddress;
    const isVerified = accommodation.status === ListingStatus.LIVE;
    const statusLabel = accommodation.status?.replace('_', ' ') || 'Draft';

    // Google Maps link
    const mapsQuery = encodeURIComponent(`${accommodation.address}, ${accommodation.city}, ${accommodation.pincode}`);
    const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${mapsQuery}`;

    return (
        <div className="max-w-5xl mx-auto space-y-8 pb-24 animate-in fade-in px-4">
            {/* Header */}
            <div className="flex items-center gap-4 flex-wrap">
                <Button variant="ghost" onClick={() => navigate('/super-admin/supply')}>
                    <ArrowLeft className="w-5 h-5 mr-2" /> Back to Supply
                </Button>
                <div className="flex-1">
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <Home className="w-6 h-6 text-indigo-600" />
                        {accommodation.name}
                        {isVerified && <CheckCircle className="w-5 h-5 text-green-500" />}
                    </h1>
                    <p className="text-gray-500 text-sm">Property ID: {accommodation.id}</p>
                </div>
                <Badge variant={isVerified ? 'success' : 'warning'} className="text-sm px-3 py-1">
                    {statusLabel}
                </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                {/* Main Content */}
                <div className="md:col-span-2 space-y-8">

                    {/* A. Property Overview */}
                    <Card className="p-6">
                        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                            <Building2 className="w-5 h-5 text-indigo-600" /> Property Overview
                        </h3>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <label className="block text-gray-500">Listing Type</label>
                                <span className="font-medium">{accommodation.type || 'PG'}</span>
                            </div>
                            <div>
                                <label className="block text-gray-500">Gender</label>
                                <span className="font-medium">{accommodation.gender || 'Unisex'}</span>
                            </div>
                            <div>
                                <label className="block text-gray-500">Owner ID</label>
                                <span className="font-mono text-xs bg-gray-100 p-1 rounded">{accommodation.ownerId}</span>
                            </div>
                            <div>
                                <label className="block text-gray-500">Room Sharing</label>
                                <span className="font-medium">{accommodation.sharing || 'Single'}</span>
                            </div>
                        </div>
                    </Card>

                    {/* B. Image Gallery */}
                    <Card className={`p-6 border-l-4 ${hasReviewedImages ? 'border-l-green-500' : 'border-l-orange-500'}`}>
                        <div className="flex justify-between items-start mb-4">
                            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                                <Grid className="w-5 h-5 text-indigo-600" />
                                Image Gallery
                                <span className="text-xs font-normal text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">{images.length} Images</span>
                            </h3>
                            {!hasReviewedImages && (
                                <span className="text-xs text-orange-600 font-bold animate-pulse">Review Required</span>
                            )}
                        </div>

                        {images.length > 0 ? (
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                {images.map((img: string, i: number) => (
                                    <div key={i} className="aspect-video bg-gray-100 rounded-lg overflow-hidden border border-gray-200">
                                        <img src={img} alt={`Photo ${i + 1}`} className="w-full h-full object-cover hover:scale-105 transition-transform duration-300 cursor-zoom-in" />
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="p-8 text-center text-gray-400 bg-gray-50 rounded-lg">No images uploaded.</div>
                        )}

                        <div className="mt-6 pt-4 border-t border-gray-100">
                            <label className="flex items-center gap-3 cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="w-5 h-5 text-indigo-600 rounded focus:ring-indigo-500"
                                    checked={hasReviewedImages}
                                    onChange={(e) => setHasReviewedImages(e.target.checked)}
                                />
                                <span className="text-sm font-medium text-gray-700">
                                    I have reviewed all uploaded images and confirmed they look authentic.
                                </span>
                            </label>
                        </div>
                    </Card>

                    {/* C. Address Verification */}
                    <Card className={`p-6 border-l-4 ${hasVerifiedAddress ? 'border-l-green-500' : 'border-l-orange-500'}`}>
                        <div className="flex justify-between items-start mb-4">
                            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                                <MapPin className="w-5 h-5 text-indigo-600" /> Location Details
                            </h3>
                            {!hasVerifiedAddress && (
                                <span className="text-xs text-orange-600 font-bold animate-pulse">Verify Required</span>
                            )}
                        </div>
                        <div className="bg-gray-50 p-4 rounded-lg border border-gray-200 mb-4">
                            <p className="font-medium text-gray-900">{accommodation.name}</p>
                            <p className="text-gray-600 mt-1">{accommodation.address}</p>
                            <p className="text-gray-600">{accommodation.locality}, {accommodation.area}</p>
                            <p className="text-gray-500 text-sm mt-1">{accommodation.city}, {accommodation.state} - {accommodation.pincode}</p>
                        </div>

                        <a
                            href={mapsUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center px-4 py-2 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors font-medium text-sm"
                        >
                            <ExternalLink className="w-4 h-4 mr-2" /> Open in Google Maps
                        </a>

                        <div className="mt-6 pt-4 border-t border-gray-100">
                            <label className="flex items-center gap-3 cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="w-5 h-5 text-indigo-600 rounded focus:ring-indigo-500"
                                    checked={hasVerifiedAddress}
                                    onChange={(e) => setHasVerifiedAddress(e.target.checked)}
                                />
                                <span className="text-sm font-medium text-gray-700">
                                    I have verified the address on Google Maps and it appears valid.
                                </span>
                            </label>
                        </div>
                    </Card>

                    {/* D. Amenities */}
                    <Card className="p-6">
                        <h3 className="text-lg font-bold text-gray-900 mb-4">Amenities & Facilities</h3>
                        <div className="flex flex-wrap gap-2">
                            {accommodation.amenities && accommodation.amenities.length > 0 ? (
                                accommodation.amenities.map((am, i) => (
                                    <span key={i} className="px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium">{am}</span>
                                ))
                            ) : (
                                <p className="text-gray-400">No amenities listed.</p>
                            )}
                        </div>
                    </Card>
                </div>

                {/* Sidebar Info */}
                <div className="space-y-6">
                    {/* Owner Contact - FULL DETAILS FOR SUPER ADMIN */}
                    <Card className="p-6 border-t-4 border-t-indigo-500">
                        <h3 className="text-sm font-bold text-gray-500 uppercase mb-4">Owner Details (Admin Only)</h3>
                        <div className="space-y-4">
                            {/* Owner Name */}
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-indigo-50 rounded-full text-indigo-600">
                                    <UserIcon className="w-4 h-4" />
                                </div>
                                <div>
                                    <p className="text-sm font-bold text-gray-900">{owner?.name || 'Loading...'}</p>
                                    <p className="text-xs text-gray-500">Owner ID: {accommodation.ownerId?.slice(0, 12)}...</p>
                                </div>
                            </div>
                            {/* Email - VISIBLE */}
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-indigo-50 rounded-full text-indigo-600">
                                    <Mail className="w-4 h-4" />
                                </div>
                                <div className="truncate flex-1">
                                    <p className="text-sm font-bold text-gray-900">{owner?.email || 'Not available'}</p>
                                    {owner?.email && (
                                        <a href={`mailto:${owner.email}`} className="text-xs text-indigo-600 hover:underline">Email Owner</a>
                                    )}
                                </div>
                            </div>
                            {/* Phone - VISIBLE */}
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-indigo-50 rounded-full text-indigo-600">
                                    <Phone className="w-4 h-4" />
                                </div>
                                <div>
                                    <p className="text-sm font-bold text-gray-900">{owner?.phone || accommodation.contactPhone || 'Not available'}</p>
                                    {(owner?.phone || accommodation.contactPhone) && (
                                        <a href={`tel:${owner?.phone || accommodation.contactPhone}`} className="text-xs text-indigo-600 hover:underline">Call Owner</a>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Admin Action Buttons */}
                        <div className="mt-6 pt-4 border-t border-gray-100 flex flex-wrap gap-2">
                            {owner?.phone && (
                                <a href={`tel:${owner.phone}`} className="inline-flex items-center px-3 py-1.5 bg-green-50 text-green-700 rounded-lg text-xs font-medium hover:bg-green-100">
                                    <Phone className="w-3 h-3 mr-1" /> Call
                                </a>
                            )}
                            {owner?.email && (
                                <a href={`mailto:${owner.email}`} className="inline-flex items-center px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium hover:bg-blue-100">
                                    <Mail className="w-3 h-3 mr-1" /> Email
                                </a>
                            )}
                            <button className="inline-flex items-center px-3 py-1.5 bg-orange-50 text-orange-700 rounded-lg text-xs font-medium hover:bg-orange-100">
                                <Flag className="w-3 h-3 mr-1" /> Flag Owner
                            </button>
                        </div>
                    </Card>

                    {/* Pricing */}
                    <Card className="p-6">
                        <h3 className="text-sm font-bold text-gray-500 uppercase mb-4">Pricing</h3>
                        <div className="space-y-3">
                            <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                                <span className="text-gray-600">Monthly Rent</span>
                                <span className="text-xl font-bold text-gray-900">₹{accommodation.price}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600">Room Type</span>
                                <span className="font-medium">{accommodation.sharing || 'Single'}</span>
                            </div>
                        </div>
                    </Card>
                </div>
            </div>

            {/* Verification Actions (Sticky Footer) */}
            <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-lg z-40 md:pl-64">
                <div className="max-w-5xl mx-auto flex items-center justify-between flex-wrap gap-4">
                    <div className="flex items-center gap-2">
                        <Shield className="w-5 h-5 text-gray-400" />
                        <span className="text-sm text-gray-500">
                            {isVerified
                                ? "This listing is live. You can reject it to take it down."
                                : canVerify
                                    ? "All checks complete. Ready to verify."
                                    : "Please review images and verify address before approving."}
                        </span>
                    </div>
                    <div className="flex gap-4">
                        <Button
                            variant="outline"
                            className="border-red-200 text-red-600 hover:bg-red-50 hover:border-red-300"
                            onClick={() => setIsRejectModalOpen(true)}
                            disabled={isProcessing}
                        >
                            <XCircle className="w-4 h-4 mr-2" /> Reject Listing
                        </Button>

                        {!isVerified && (
                            <Button
                                className={`transition-all ${canVerify ? 'bg-green-600 hover:bg-green-700' : 'bg-gray-300 cursor-not-allowed'}`}
                                disabled={!canVerify || isProcessing}
                                onClick={handleVerify}
                            >
                                <CheckCircle className="w-4 h-4 mr-2" /> {isProcessing ? 'Processing...' : 'Verify & Publish'}
                            </Button>
                        )}
                    </div>
                </div>
            </div>

            {/* Rejection Modal */}
            {isRejectModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
                    <Card className="w-full max-w-md p-6 animate-in zoom-in-95">
                        <div className="flex items-center gap-2 mb-4 text-red-600">
                            <AlertTriangle className="w-6 h-6" />
                            <h3 className="text-lg font-bold">Reject Listing</h3>
                        </div>
                        <p className="text-sm text-gray-600 mb-4">
                            Please provide a reason for rejecting this listing. This will be sent to the owner.
                        </p>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Reason for Rejection <span className="text-red-500">*</span></label>
                                <select
                                    className="w-full border border-gray-300 rounded-lg p-2 mb-2 focus:ring-red-500 focus:border-red-500"
                                    onChange={(e) => setRejectionReason(e.target.value)}
                                    value={rejectionReason.includes('Other:') ? '' : rejectionReason}
                                >
                                    <option value="">Select a reason...</option>
                                    <option value="Fake or misleading images">Fake or misleading images</option>
                                    <option value="Invalid or incomplete address">Invalid or incomplete address</option>
                                    <option value="Duplicate listing">Duplicate listing</option>
                                    <option value="Incomplete information">Incomplete information</option>
                                    <option value="Suspicious pricing">Suspicious pricing</option>
                                </select>
                                <textarea
                                    className="w-full border border-gray-300 rounded-lg p-3 focus:ring-red-500 focus:border-red-500 h-24"
                                    placeholder="Additional notes (optional)..."
                                    value={rejectionReason}
                                    onChange={(e) => setRejectionReason(e.target.value)}
                                />
                            </div>

                            <div className="flex justify-end gap-3">
                                <Button variant="ghost" onClick={() => setIsRejectModalOpen(false)}>Cancel</Button>
                                <Button
                                    className="bg-red-600 hover:bg-red-700 text-white"
                                    disabled={!rejectionReason.trim() || isProcessing}
                                    onClick={handleReject}
                                >
                                    {isProcessing ? 'Processing...' : 'Confirm Rejection'}
                                </Button>
                            </div>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
};
