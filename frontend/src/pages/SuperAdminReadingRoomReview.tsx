
// pages/SuperAdminReadingRoomReview.tsx

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ReadingRoom, ListingStatus, User } from '../types';
import { supplyService } from '../services/supplyService';
import { userService } from '../services/userService';
import { Card, Button, Badge, Modal } from '../components/UI';
import { MapPin, User as UserIcon, Phone, Mail, Building2, CheckCircle, XCircle, Grid, ArrowLeft, AlertTriangle, Shield, ExternalLink, Flag, Eye } from 'lucide-react';

// --- Helper Functions (Moved outside component for stability) ---
const parseAmenities = (amenities: string[] | string | undefined | null): string[] => {
    if (!amenities) return [];
    if (Array.isArray(amenities)) return amenities;
    try {
        // Handle postgres array string format like "{WiFi,AC}" if necessary, though explicit JSON is more common
        if (typeof amenities === 'string' && amenities.startsWith('{') && amenities.endsWith('}')) {
            return amenities.slice(1, -1).split(',');
        }
        return JSON.parse(amenities);
    } catch (e) {
        return typeof amenities === 'string' ? [amenities] : [];
    }
};

const getVenueImages = (venue: ReadingRoom): string[] => {
    if (!venue) return [];
    try {
        if (Array.isArray(venue.images)) return venue.images;
        if (typeof venue.images === 'string') {
            // Check if it's a JSON string
            if (venue.images.startsWith('[')) {
                return JSON.parse(venue.images);
            }
            // Fallback for single image string
            return [venue.images];
        }
        // Fallback to legacy field
        if (venue.imageUrl) return [venue.imageUrl];
        return [];
    } catch (e) {
        console.error("Error parsing images", e);
        return venue.imageUrl ? [venue.imageUrl] : [];
    }
};

export const SuperAdminReadingRoomReview = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [venue, setVenue] = useState<ReadingRoom | null>(null);
    const [owner, setOwner] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Safety Checks
    const [hasReviewedImages, setHasReviewedImages] = useState(false);
    const [hasVerifiedAddress, setHasVerifiedAddress] = useState(false);

    // Actions
    const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
    const [rejectionReason, setRejectionReason] = useState('');

    useEffect(() => {
        if (id) fetchVenue(id);
    }, [id]);

    const fetchVenue = async (venueId: string) => {
        setLoading(true);
        try {
            const data = await supplyService.getReadingRoomById(venueId);
            setVenue(data);
            // Fetch owner details
            if (data.ownerId) {
                const ownerData = await userService.getUserById(data.ownerId);
                setOwner(ownerData);
            }
        } catch (err) {
            console.error("Error fetching venue details:", err);
            setError('Failed to load venue details.');
        } finally {
            setLoading(false);
        }
    };

    const handleVerify = async () => {
        if (!venue) return;
        if (!confirm('Are you sure you want to verify this listing? It will become visible to users immediately.')) return;

        try {
            await supplyService.verifyEntity(venue.id, 'room');
            alert('Venue verified successfully!');
            navigate('/super-admin/supply'); // Return to list
        } catch (err) {
            alert('Failed to verify.');
        }
    };

    const handleReject = async () => {
        if (!venue || !rejectionReason.trim()) return;

        try {
            await supplyService.rejectEntity(venue.id, 'room', rejectionReason);
            alert('Venue rejected and owner notified.');
            setIsRejectModalOpen(false);
            navigate('/super-admin/supply');
        } catch (err) {
            alert('Failed to reject.');
        }
    };

    // --- Safe Rendering Logic ---
    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh]">
                <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mb-4"></div>
                <p className="text-gray-500">Loading details...</p>
            </div>
        );
    }

    if (error || !venue) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh]">
                <XCircle className="w-12 h-12 text-red-500 mb-4" />
                <h2 className="text-xl font-bold text-gray-900 mb-2">Error</h2>
                <p className="text-gray-500">{error || 'Venue not found'}</p>
                <Button variant="outline" className="mt-4" onClick={() => navigate('/super-admin/supply')}>
                    Go Back
                </Button>
            </div>
        );
    }

    // Prepare safe data
    const images = getVenueImages(venue);
    const safeAmenities = parseAmenities(venue.amenities);

    return (
        <div className="max-w-5xl mx-auto space-y-8 pb-20 animate-in fade-in">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="ghost" onClick={() => navigate('/super-admin/supply')}>
                    <ArrowLeft className="w-5 h-5 mr-2" /> Back to Supply
                </Button>
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        {venue.name}
                        {venue.isVerified && <CheckCircle className="w-5 h-5 text-green-500" />}
                    </h1>
                    <p className="text-gray-500 text-sm">Property ID: {venue.id}</p>
                </div>
                <div className="ml-auto">
                    <Badge variant={venue.isVerified ? 'success' : 'warning'} className="text-sm px-3 py-1">
                        {venue.isVerified ? 'Verified' : 'Verification Pending'}
                    </Badge>
                </div>
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
                                <span className="font-medium">Reading Room</span>
                            </div>
                            <div>
                                <label className="block text-gray-500">Subscription Plan</label>
                                <span className="font-medium text-indigo-600">{venue.featuredPlan || 'Standard'}</span>
                            </div>
                            <div>
                                <label className="block text-gray-500">Owner ID</label>
                                <span className="font-mono text-xs bg-gray-100 p-1 rounded">{venue.ownerId}</span>
                            </div>
                            <div>
                                <label className="block text-gray-500">Submission Date</label>
                                <span className="font-medium">
                                    {(venue as any).created_at || (venue as any).createdAt
                                        ? new Date((venue as any).created_at || (venue as any).createdAt).toLocaleDateString('en-IN', {
                                            day: 'numeric',
                                            month: 'short',
                                            year: 'numeric'
                                        })
                                        : 'N/A'}
                                </span>
                            </div>
                        </div>
                    </Card>

                    {/* B. Image Gallery */}
                    <Card className={`p-6 border-l-4 ${hasReviewedImages ? 'border-l-green-500' : 'border-l-orange-500 transition-colors'}`}>
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
                                        <img src={img} alt={`Venue ${i}`} className="w-full h-full object-cover hover:scale-105 transition-transform duration-300 cursor-zoom-in" />
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
                            <p className="font-medium text-gray-900">{venue.name}</p>
                            <p className="text-gray-600 mt-1">{venue.address}</p>
                            <p className="text-gray-600">{venue.area}, {venue.city}</p>
                            <p className="text-gray-500 text-sm mt-1">{venue.state} - {venue.pincode}</p>
                        </div>

                        <a
                            href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${venue.address}, ${venue.city}, ${venue.pincode}`)}`}
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

                    {/* E. Owner Notes */}
                    <Card className="p-6">
                        <h3 className="text-lg font-bold text-gray-900 mb-2">Owner Description</h3>
                        <p className="text-gray-600 text-sm leading-relaxed">
                            {venue.description || 'No description provided.'}
                        </p>
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
                                    <p className="text-xs text-gray-500">Owner ID: {venue.ownerId?.slice(0, 12)}...</p>
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
                                    <p className="text-sm font-bold text-gray-900">{owner?.phone || venue.contactPhone || 'Not available'}</p>
                                    {(owner?.phone || venue.contactPhone) && (
                                        <a href={`tel:${owner?.phone || venue.contactPhone}`} className="text-xs text-indigo-600 hover:underline">Call Owner</a>
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

                    {/* D. Pricing & Capacity */}
                    <Card className="p-6">
                        <h3 className="text-sm font-bold text-gray-500 uppercase mb-4">Pricing & Capacity</h3>
                        <div className="space-y-3">
                            <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                                <span className="text-gray-600">Monthly Price</span>
                                <span className="text-lg font-bold text-gray-900">₹{venue.priceStart}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <span className="text-gray-600">Amenities</span>
                                <span className="font-medium">{safeAmenities.length} Included</span>
                            </div>
                            <div className="flex flex-wrap gap-1 mt-2">
                                {safeAmenities.slice(0, 5).map((am, i) => (
                                    <span key={i} className="text-[10px] bg-gray-100 px-2 py-1 rounded text-gray-600">{am}</span>
                                ))}
                                {safeAmenities.length > 5 && <span className="text-[10px] text-gray-400">+{safeAmenities.length - 5} more</span>}
                            </div>
                        </div>
                    </Card>
                </div>
            </div>

            {/* 4. Verification Actions (Sticky Footer) */}
            <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-lg z-40 md:pl-64">
                <div className="max-w-5xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Shield className="w-5 h-5 text-gray-400" />
                        <span className="text-sm text-gray-500">
                            {venue.isVerified
                                ? "This listing is live. You can reject it to take it down."
                                : "Review all details carefully before verifying."}
                        </span>
                    </div>
                    <div className="flex gap-4">
                        <Button
                            variant="outline"
                            className="border-red-200 text-red-600 hover:bg-red-50 hover:border-red-300"
                            onClick={() => setIsRejectModalOpen(true)}
                        >
                            <XCircle className="w-4 h-4 mr-2" /> Reject Listing
                        </Button>

                        {!venue.isVerified && (
                            <Button
                                className={`transition-all ${hasReviewedImages && hasVerifiedAddress ? 'bg-green-600 hover:bg-green-700' : 'bg-gray-300 cursor-not-allowed'}`}
                                disabled={!hasReviewedImages || !hasVerifiedAddress}
                                onClick={handleVerify}
                            >
                                <CheckCircle className="w-4 h-4 mr-2" /> Verify Listing
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
                                <textarea
                                    className="w-full border border-gray-300 rounded-lg p-3 focus:ring-red-500 focus:border-red-500 h-32"
                                    placeholder="e.g. Broken images, Fake address, Duplicate listing..."
                                    value={rejectionReason}
                                    onChange={(e) => setRejectionReason(e.target.value)}
                                />
                            </div>

                            <div className="flex justify-end gap-3">
                                <Button variant="ghost" onClick={() => setIsRejectModalOpen(false)}>Cancel</Button>
                                <Button
                                    className="bg-red-600 hover:bg-red-700 text-white"
                                    disabled={!rejectionReason.trim()}
                                    onClick={handleReject}
                                >
                                    Confirm Rejection
                                </Button>
                            </div>
                        </div>
                    </Card>
                </div>
            )}
        </div>
    );
};

