/**
 * Subscription Plans Service - API calls for venue listing subscription plans
 */

import api from './api';

export interface SubscriptionPlan {
    id: string;
    name: string;
    description: string | null;
    price: number;
    durationDays: number;
    features: string[];
    isActive: boolean;
    isDefault: boolean;
    createdBy: string;
    createdAt: string;
}

export interface CreateSubscriptionPlanRequest {
    name: string;
    description?: string;
    price: number;
    duration_days?: number;
    features?: string[];
    is_active?: boolean;
    is_default?: boolean;
}

export interface UpdateSubscriptionPlanRequest {
    name?: string;
    description?: string;
    price?: number;
    duration_days?: number;
    features?: string[];
    is_active?: boolean;
    is_default?: boolean;
}

// Transform backend snake_case to frontend camelCase
const transformPlan = (plan: any): SubscriptionPlan => ({
    id: plan.id,
    name: plan.name,
    description: plan.description,
    price: plan.price,
    durationDays: plan.duration_days,
    features: plan.features || [],
    isActive: plan.is_active,
    isDefault: plan.is_default,
    createdBy: plan.created_by,
    createdAt: plan.created_at
});

export const subscriptionService = {
    /**
     * Get all subscription plans
     */
    async getPlans(includeInactive = false): Promise<SubscriptionPlan[]> {
        try {
            const response = await api.get(`/subscriptions/plans?include_inactive=${includeInactive}`);
            return (response.data || []).map(transformPlan);
        } catch (error) {
            console.error('Failed to fetch subscription plans:', error);
            return [];
        }
    },

    /**
     * Create a new subscription plan (Super Admin only)
     */
    async createPlan(plan: CreateSubscriptionPlanRequest): Promise<SubscriptionPlan | null> {
        try {
            const response = await api.post('/subscriptions/plans', plan);
            return transformPlan(response.data);
        } catch (error) {
            console.error('Failed to create subscription plan:', error);
            throw error;
        }
    },

    /**
     * Update an existing subscription plan (Super Admin only)
     */
    async updatePlan(planId: string, updates: UpdateSubscriptionPlanRequest): Promise<SubscriptionPlan | null> {
        try {
            const response = await api.put(`/subscriptions/plans/${planId}`, updates);
            return transformPlan(response.data);
        } catch (error) {
            console.error('Failed to update subscription plan:', error);
            throw error;
        }
    },

    /**
     * Delete a subscription plan (Super Admin only)
     */
    async deletePlan(planId: string): Promise<boolean> {
        try {
            await api.delete(`/subscriptions/plans/${planId}`);
            return true;
        } catch (error) {
            console.error('Failed to delete subscription plan:', error);
            throw error;
        }
    }
};

export default subscriptionService;
