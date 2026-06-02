/**
 * Trust & Safety Service
 * 
 * All functions:
 * - Call backend API
 * - Persist state
 * - Log to audit trail
 * 
 * NO UI-ONLY ACTIONS
 */

import api from './api';

// =========== TYPES ===========

export type TrustFlagType =
    | 'weak_description'
    | 'fake_address'
    | 'suspicious_activity'
    | 'missing_phone'
    | 'missing_images'
    | 'policy_violation'
    | 'other';

export type TrustFlagStatus =
    | 'active'
    | 'owner_resubmitted'
    | 'resolved'
    | 'rejected'
    | 'escalated';

export type ReminderType =
    | 'phone'
    | 'email'
    | 'address'
    | 'kyc'
    | 'profile'
    | 'document';

export type ReminderStatus = 'pending' | 'acknowledged' | 'completed' | 'expired';

export type TrustStatus = 'CLEAR' | 'FLAGGED' | 'UNDER_REVIEW' | 'SUSPENDED';

export interface TrustFlag {
    id: string;
    entity_type: string;
    entity_id: string;
    entity_name: string;
    flag_type: TrustFlagType;
    custom_reason?: string;
    raised_by: string;
    raised_by_name?: string;
    status: TrustFlagStatus;
    resolution_notes?: string;
    resolved_by?: string;
    resolved_by_name?: string;
    created_at: string;
    updated_at?: string;
    resolved_at?: string;
    owner_notes?: string;
    resubmitted_at?: string;
}

export interface Reminder {
    id: string;
    user_id: string;
    user_name?: string;
    user_email?: string;
    reminder_type: ReminderType;
    missing_fields?: string;
    message?: string;
    sent_by: string;
    sent_by_name?: string;
    status: ReminderStatus;
    blocks_listings: boolean;
    blocks_payments: boolean;
    blocks_bookings: boolean;
    sent_at: string;
    acknowledged_at?: string;
    completed_at?: string;
    email_sent: boolean;
    email_sent_at?: string;
}

export interface AuditLogEntry {
    id: string;
    actor_id: string;
    actor_name?: string;
    actor_role: string;
    action_type: string;
    action_description?: string;
    entity_type?: string;
    entity_id?: string;
    entity_name?: string;
    metadata?: string;
    timestamp: string;
}

export interface VenueTrustStatus {
    entity_id: string;
    entity_type: string;
    entity_name: string;
    trust_status: TrustStatus;
    is_flagged: boolean;
    active_flags: TrustFlag[];
    can_promote: boolean;
    can_accept_payments: boolean;
    is_visible_to_users: boolean;
}

export interface UserBlocks {
    has_blocks: boolean;
    blocks_listings: boolean;
    blocks_payments: boolean;
    blocks_bookings: boolean;
    pending_reminders: number;
    reminder_types: string[];
}

// =========== FLAG OPERATIONS ===========

export const trustService = {
    // Get all flags
    async getAllFlags(status?: string, entityType?: string): Promise<TrustFlag[]> {
        const params = new URLSearchParams();
        if (status) params.append('status', status);
        if (entityType) params.append('entity_type', entityType);

        const response = await api.get(`/api/trust/flags?${params.toString()}`);
        return response.data;
    },

    // Create a new flag (Super Admin only)
    async createFlag(
        entityType: string,
        entityId: string,
        flagType: TrustFlagType,
        customReason?: string,
        actorId?: string,
        actorName?: string
    ): Promise<TrustFlag> {
        const params = new URLSearchParams({
            actor_id: actorId || 'super_admin',
            actor_name: actorName || 'Super Admin'
        });

        const response = await api.post(`/api/trust/flags?${params.toString()}`, {
            entity_type: entityType,
            entity_id: entityId,
            flag_type: flagType,
            custom_reason: customReason
        });
        return response.data;
    },

    // Resolve a flag (Super Admin only)
    async resolveFlag(
        flagId: string,
        action: 'approve' | 'reject' | 'escalate',
        notes?: string,
        actorId?: string,
        actorName?: string
    ): Promise<TrustFlag> {
        const params = new URLSearchParams({
            actor_id: actorId || 'super_admin',
            actor_name: actorName || 'Super Admin'
        });

        const response = await api.patch(`/api/trust/flags/${flagId}/resolve?${params.toString()}`, {
            action,
            notes
        });
        return response.data;
    },

    // Owner resubmits for review
    async ownerResubmit(
        flagId: string,
        notes: string,
        ownerId: string,
        ownerName: string
    ): Promise<TrustFlag> {
        const params = new URLSearchParams({
            owner_id: ownerId,
            owner_name: ownerName
        });

        const response = await api.post(`/api/trust/flags/${flagId}/resubmit?${params.toString()}`, {
            notes
        });
        return response.data;
    },

    // Reinstate a suspended venue (Super Admin only)
    async reinstateFlag(
        flagId: string,
        notes?: string,
        actorId?: string,
        actorName?: string
    ): Promise<TrustFlag> {
        const params = new URLSearchParams({
            actor_id: actorId || 'super_admin',
            actor_name: actorName || 'Super Admin'
        });
        if (notes) params.append('notes', notes);

        const response = await api.patch(`/api/trust/flags/${flagId}/reinstate?${params.toString()}`);
        return response.data;
    },

    // Get owner's flags
    async getOwnerFlags(ownerId: string): Promise<TrustFlag[]> {
        const response = await api.get(`/api/trust/owner/flags?owner_id=${ownerId}`);
        return response.data;
    },

    // =========== REMINDER OPERATIONS ===========

    // Get all reminders
    async getAllReminders(status?: string): Promise<Reminder[]> {
        const params = status ? `?status=${status}` : '';
        const response = await api.get(`/api/trust/reminders${params}`);
        return response.data;
    },

    // Send reminder (Super Admin only)
    async sendReminder(
        userId: string,
        reminderType: ReminderType,
        missingFields?: string[],
        message?: string,
        blocksListings = true,
        blocksPayments = true,
        blocksBookings = false,
        actorId?: string,
        actorName?: string
    ): Promise<Reminder> {
        const params = new URLSearchParams({
            actor_id: actorId || 'super_admin',
            actor_name: actorName || 'Super Admin'
        });

        const response = await api.post(`/api/trust/reminders?${params.toString()}`, {
            user_id: userId,
            reminder_type: reminderType,
            missing_fields: missingFields ? JSON.stringify(missingFields) : null,
            message,
            blocks_listings: blocksListings,
            blocks_payments: blocksPayments,
            blocks_bookings: blocksBookings
        });
        return response.data;
    },

    // Complete a reminder (user verifies)
    async completeReminder(reminderId: string, userId: string): Promise<Reminder> {
        const response = await api.patch(`/api/trust/reminders/${reminderId}/complete?user_id=${userId}`);
        return response.data;
    },

    // Get user's reminders
    async getUserReminders(userId: string): Promise<Reminder[]> {
        const response = await api.get(`/api/trust/user/reminders?user_id=${userId}`);
        return response.data;
    },

    // Check user blocks
    async checkUserBlocks(userId: string): Promise<UserBlocks> {
        const response = await api.get(`/api/trust/user/has-blocks?user_id=${userId}`);
        return response.data;
    },

    // =========== AUDIT LOG ===========

    async getAuditLog(filters?: {
        startDate?: string;
        endDate?: string;
        actorId?: string;
        actionType?: string;
        entityType?: string;
        limit?: number;
        offset?: number;
    }): Promise<{ total: number; entries: AuditLogEntry[]; limit: number; offset: number }> {
        const params = new URLSearchParams();
        if (filters?.startDate) params.append('start_date', filters.startDate);
        if (filters?.endDate) params.append('end_date', filters.endDate);
        if (filters?.actorId) params.append('actor_id', filters.actorId);
        if (filters?.actionType) params.append('action_type', filters.actionType);
        if (filters?.entityType) params.append('entity_type', filters.entityType);
        if (filters?.limit) params.append('limit', String(filters.limit));
        if (filters?.offset) params.append('offset', String(filters.offset));

        const response = await api.get(`/api/trust/audit-log?${params.toString()}`);
        return response.data;
    },

    // Get audit log for specific entity (owner view)
    async getEntityAuditLog(entityType: string, entityId: string): Promise<AuditLogEntry[]> {
        const response = await api.get(`/api/trust/audit-log/entity/${entityType}/${entityId}`);
        return response.data;
    },

    // =========== VENUE TRUST STATUS ===========

    async getVenueTrustStatus(entityType: string, entityId: string): Promise<VenueTrustStatus> {
        const response = await api.get(`/api/trust/venue/${entityType}/${entityId}/status`);
        return response.data;
    }
};
