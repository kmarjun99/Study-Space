/**
 * Boost Service - API calls for boost plans and requests
 * Super Admin creates plans, Owners request boosts, Super Admin approves
 */
import api from './api';

// Types matching backend
export interface BoostPlan {
    id: string;
    name: string;
    description?: string;
    price: number;
    durationDays: number;
    applicableTo: 'reading_room' | 'accommodation' | 'both';
    placement: 'featured_section' | 'top_list' | 'banner';
    visibilityWeight: number;
    status: 'draft' | 'active' | 'inactive';
    createdBy: string;
    createdAt: string;
}

export interface BoostRequest {
    id: string;
    ownerId: string;
    ownerName?: string;
    venueId: string;
    venueType: 'reading_room' | 'accommodation';
    venueName?: string;
    boostPlanId: string;
    planName?: string;
    price: number;
    durationDays: number;
    placement?: string;
    paymentId?: string;
    status: 'initiated' | 'payment_pending' | 'paid' | 'admin_review' | 'approved' | 'rejected' | 'active' | 'expired';
    requestedAt: string;
    paidAt?: string;
    approvedAt?: string;
    approvedBy?: string;
    expiryDate?: string;
    adminNotes?: string;
    rejectionReason?: string;
}

export interface FeaturedListing {
    venueId: string;
    venueType: string;
    venueName: string;
    placement: string;
    expiryDate: string;
}

// Transform backend snake_case to frontend camelCase
const transformPlan = (plan: any): BoostPlan => ({
    id: plan.id,
    name: plan.name,
    description: plan.description,
    price: plan.price,
    durationDays: plan.duration_days,
    applicableTo: plan.applicable_to,
    placement: plan.placement,
    visibilityWeight: plan.visibility_weight,
    status: plan.status,
    createdBy: plan.created_by,
    createdAt: plan.created_at
});

const transformRequest = (req: any): BoostRequest => ({
    id: req.id,
    ownerId: req.owner_id,
    ownerName: req.owner_name,
    venueId: req.venue_id,
    venueType: req.venue_type,
    venueName: req.venue_name,
    boostPlanId: req.boost_plan_id,
    planName: req.plan_name,
    price: req.price,
    durationDays: req.duration_days,
    placement: req.placement,
    paymentId: req.payment_id,
    status: req.status,
    requestedAt: req.requested_at,
    paidAt: req.paid_at,
    approvedAt: req.approved_at,
    approvedBy: req.approved_by,
    expiryDate: req.expiry_date,
    adminNotes: req.admin_notes,
    rejectionReason: req.rejection_reason
});

export const boostService = {
    // ============================================
    // BOOST PLANS (Super Admin + Owners read)
    // ============================================

    /**
     * Get all active boost plans.
     * Owners see only ACTIVE plans.
     */
    getPlans: async (includeInactive: boolean = false): Promise<BoostPlan[]> => {
        const response = await api.get(`/boost/plans?include_inactive=${includeInactive}`);
        return (response.data || []).map(transformPlan);
    },

    /**
     * Create a new boost plan. Super Admin only.
     */
    createPlan: async (plan: Partial<BoostPlan>): Promise<BoostPlan> => {
        const payload = {
            name: plan.name,
            description: plan.description,
            price: plan.price,
            duration_days: plan.durationDays,
            applicable_to: plan.applicableTo?.toLowerCase(),
            placement: plan.placement?.toLowerCase(),
            visibility_weight: plan.visibilityWeight,
            status: plan.status?.toLowerCase()
        };
        const response = await api.post('/boost/plans', payload);
        return transformPlan(response.data);
    },

    /**
     * Update a boost plan. Super Admin only.
     */
    updatePlan: async (planId: string, updates: Partial<BoostPlan>): Promise<BoostPlan> => {
        const payload: any = {};
        if (updates.name !== undefined) payload.name = updates.name;
        if (updates.description !== undefined) payload.description = updates.description;
        if (updates.price !== undefined) payload.price = updates.price;
        if (updates.durationDays !== undefined) payload.duration_days = updates.durationDays;
        if (updates.applicableTo !== undefined) payload.applicable_to = updates.applicableTo.toLowerCase();
        if (updates.placement !== undefined) payload.placement = updates.placement.toLowerCase();
        if (updates.visibilityWeight !== undefined) payload.visibility_weight = updates.visibilityWeight;
        if (updates.status !== undefined) payload.status = updates.status.toLowerCase();

        const response = await api.put(`/boost/plans/${planId}`, payload);
        return transformPlan(response.data);
    },

    /**
     * Delete a boost plan. Super Admin only.
     */
    deletePlan: async (planId: string): Promise<void> => {
        await api.delete(`/boost/plans/${planId}`);
    },

    // ============================================
    // BOOST REQUESTS (Owners)
    // ============================================

    /**
     * Create a boost request for a venue.
     * This creates a REQUEST only - NOT activation.
     */
    createRequest: async (venueId: string, venueType: 'reading_room' | 'accommodation', boostPlanId: string): Promise<BoostRequest> => {
        const payload = {
            venue_id: venueId,
            venue_type: venueType,
            boost_plan_id: boostPlanId
        };
        const response = await api.post('/boost/request', payload);
        return transformRequest(response.data);
    },

    /**
     * Get owner's boost requests.
     */
    getMyRequests: async (): Promise<BoostRequest[]> => {
        const response = await api.get('/boost/my-requests');
        return (response.data || []).map(transformRequest);
    },

    /**
     * Mark a boost request as paid with verification.
     */
    markRequestPaid: async (requestId: string, paymentData: {
        payment_id: string;
        order_id: string;
        signature: string;
    }): Promise<void> => {
        await api.put(`/boost/request/${requestId}/pay`, paymentData);
    },

    // ============================================
    // BOOST REQUESTS (Super Admin)
    // ============================================

    /**
     * Get all boost requests. Super Admin only.
     */
    getAllRequests: async (statusFilter?: string): Promise<BoostRequest[]> => {
        const url = statusFilter ? `/boost/requests?status_filter=${statusFilter}` : '/boost/requests';
        const response = await api.get(url);
        return (response.data || []).map(transformRequest);
    },

    /**
     * Approve a boost request. Super Admin only.
     */
    approveRequest: async (requestId: string, adminNotes?: string): Promise<void> => {
        await api.put(`/boost/requests/${requestId}/approve`, { admin_notes: adminNotes });
    },

    /**
     * Reject a boost request. Super Admin only.
     */
    rejectRequest: async (requestId: string, reason: string, adminNotes?: string): Promise<void> => {
        await api.put(`/boost/requests/${requestId}/reject`, { reason, admin_notes: adminNotes });
    },

    // ============================================
    // FEATURED LISTINGS (Public)
    // ============================================

    /**
     * Get featured listings (approved + valid boosts).
     * This is what users see.
     */
    getFeaturedListings: async (venueType?: string): Promise<FeaturedListing[]> => {
        const url = venueType ? `/boost/featured?venue_type=${venueType}` : '/boost/featured';
        const response = await api.get(url);
        return (response.data || []).map((f: any) => ({
            venueId: f.venue_id,
            venueType: f.venue_type,
            venueName: f.venue_name,
            placement: f.placement,
            expiryDate: f.expiry_date
        }));
    }
};
