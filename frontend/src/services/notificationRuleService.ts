/**
 * Phase 4C — notification automation. Rule CRUD + manual evaluate + dispatch.
 * Reuses CampaignChannel / DeliveryStatus types from campaignService.
 */
import api from './api';
import type { CampaignChannel, DeliveryStatus } from './campaignService';

export type TriggerType =
    | 'BOOKING_ABANDONED'
    | 'REPEAT_SEARCH_NO_BOOKING'
    | 'AVAILABILITY_CHECKED_NO_BOOKING'
    | 'PAYMENT_FAILED';

export interface NotificationRule {
    id: string;
    slug: string;
    name: string;
    description: string | null;
    body_template: string;
    subject_template: string | null;
    trigger_type: TriggerType;
    trigger_window_minutes: number;
    min_event_count: number;
    channel: CampaignChannel;
    cooldown_hours: number;
    frequency_cap_per_user: number;
    frequency_cap_window_days: number;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface RuleInput {
    slug: string;
    name: string;
    description?: string | null;
    body_template: string;
    subject_template?: string | null;
    trigger_type: TriggerType;
    trigger_window_minutes?: number;
    min_event_count?: number;
    channel: CampaignChannel;
    cooldown_hours?: number;
    frequency_cap_per_user?: number;
    frequency_cap_window_days?: number;
    is_active?: boolean;
}

export interface RulePatch {
    name?: string;
    description?: string | null;
    body_template?: string;
    subject_template?: string | null;
    trigger_window_minutes?: number;
    min_event_count?: number;
    cooldown_hours?: number;
    frequency_cap_per_user?: number;
    frequency_cap_window_days?: number;
    is_active?: boolean;
}

export interface RuleEvaluateSummary {
    rule_id: string;
    queued: number;
    skipped_consent: number;
    skipped_cooldown: number;
    skipped_frequency: number;
    reasons: string[];
}

export interface DispatchSummary {
    delivered: number;
    failed: number;
    retried?: number;
    skipped_already_done: number;
}

export interface RuleDelivery {
    id: string;
    rule_id: string;
    user_id: string;
    channel: CampaignChannel;
    status: DeliveryStatus;
    queued_at: string;
    delivered_at: string | null;
    opened_at: string | null;
    clicked_at: string | null;
    reason: string | null;
}

export interface AutomationStatus {
    enabled: boolean;
    dispatch_batch_size: number;
    scheduler: {
        running: boolean;
        job_registered: boolean;
        frequency: string;
        next_run_time: string | null;
        trigger: string | null;
    };
    rules: {
        total: number;
        active: number;
    };
    deliveries: {
        queued: number;
        delivered_today: number;
        delivered_total: number;
        failed_total: number;
    };
    last_execution_time: string | null;
    last_error: {
        reason: string | null;
        at: string;
        channel: string;
    } | null;
}

export const notificationRuleService = {
    async automationStatus(): Promise<AutomationStatus> {
        const res = await api.get<AutomationStatus>(
            '/api/super-admin/notification-rules/automation/status',
        );
        return res.data;
    },
    async setAutomation(enabled: boolean): Promise<{ enabled: boolean }> {
        const res = await api.post<{ enabled: boolean }>(
            '/api/super-admin/notification-rules/automation/toggle',
            { enabled },
        );
        return res.data;
    },
    async list(includeInactive = true): Promise<NotificationRule[]> {
        const res = await api.get<NotificationRule[]>(
            '/api/super-admin/notification-rules',
            { params: { include_inactive: includeInactive } },
        );
        return res.data;
    },
    async create(input: RuleInput): Promise<NotificationRule> {
        const res = await api.post<NotificationRule>(
            '/api/super-admin/notification-rules', input,
        );
        return res.data;
    },
    async patch(id: string, body: RulePatch): Promise<NotificationRule> {
        const res = await api.patch<NotificationRule>(
            `/api/super-admin/notification-rules/${id}`, body,
        );
        return res.data;
    },
    async evaluate(id: string): Promise<RuleEvaluateSummary> {
        const res = await api.post<RuleEvaluateSummary>(
            `/api/super-admin/notification-rules/${id}/evaluate`,
        );
        return res.data;
    },
    async dispatchPending(limit = 100): Promise<DispatchSummary> {
        const res = await api.post<DispatchSummary>(
            '/api/super-admin/notification-rules/dispatch-pending',
            null,
            { params: { limit } },
        );
        return res.data;
    },
    async deliveries(
        id: string, status?: DeliveryStatus, limit = 100,
    ): Promise<RuleDelivery[]> {
        const res = await api.get<RuleDelivery[]>(
            `/api/super-admin/notification-rules/${id}/deliveries`,
            { params: { status, limit } },
        );
        return res.data;
    },
};
