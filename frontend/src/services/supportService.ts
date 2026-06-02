/**
 * Support Ticket Service.
 * Talks to the /api/support backend. Mirrors the ownerBillingService pattern:
 * snake_case DTOs (SupportTicketRow) describe the on-the-wire shape,
 * and a server->client mapper converts them to the camelCase SupportTicket
 * type that the existing components consume.
 *
 * IMPORTANT: the backend's SupportCategory enum is a 5-value subset
 * (PAYMENT_ISSUE, TECHNICAL_ISSUE, ACCOUNT, BOOKING, OTHER) while the
 * frontend's SupportCategory union has 11 values. Outbound categories that
 * are not in the backend enum are coerced to OTHER on the way out, and the
 * original frontend category is preserved on the way back via metaData so
 * lists still render the user-facing label.
 */
import api from './api';
import {
    SupportTicket,
    SupportCategory,
    TicketPriority,
    TicketStatus,
    UserRole,
} from '../types';

// ---- Wire types (snake_case, exactly mirrors the FastAPI response) ----------

export interface SupportTicketRow {
    id: string;
    user_id: string;
    user_name: string | null;
    user_email: string | null;
    subject: string;
    category: string;
    priority: string;
    message: string;
    status: string;
    admin_response: string | null;
    assigned_to: string | null;
    meta_data: Record<string, any> | null;
    created_at: string;
    updated_at: string;
    resolved_at: string | null;
}

// ---- Category mapping -------------------------------------------------------

// Backend categories the API actually accepts.
const BACKEND_CATEGORIES = new Set<string>([
    'PAYMENT_ISSUE',
    'TECHNICAL_ISSUE',
    'ACCOUNT',
    'BOOKING',
    'OTHER',
]);

// Map a frontend SupportCategory to a category the backend will accept.
// Anything not directly representable collapses to OTHER, and the original
// label is stashed in meta_data.originalCategory so we can restore it.
const toBackendCategory = (cat?: SupportCategory): string => {
    switch (cat) {
        case 'PAYMENT_ISSUE':
        case 'TECHNICAL_ISSUE':
        case 'ACCOUNT':
            return cat;
        case 'BOOKING_ISSUE':
            return 'BOOKING';
        case 'OTHER':
            return 'OTHER';
        default:
            // GENERAL_HELP, REFUND, SUBSCRIPTION, VENUE_ISSUE,
            // FEATURED_LISTING, CABIN_MANAGEMENT, undefined, or anything
            // else the backend doesn't know about.
            return 'OTHER';
    }
};

// Restore the original SupportCategory the user picked, preferring the
// preserved value in meta_data when available.
const fromBackendCategory = (
    cat: string,
    meta?: Record<string, any> | null,
): SupportCategory => {
    const preserved = meta?.originalCategory;
    if (typeof preserved === 'string') {
        return preserved as SupportCategory;
    }
    if (cat === 'BOOKING') return 'BOOKING_ISSUE';
    if (BACKEND_CATEGORIES.has(cat)) return cat as SupportCategory;
    return 'OTHER';
};

// ---- Role mapping -----------------------------------------------------------
// The backend doesn't track user_role on the ticket; preserve whatever the
// caller passed in via meta_data, otherwise fall back to STUDENT.
const fromBackendRole = (meta?: Record<string, any> | null): UserRole => {
    const r = meta?.userRole;
    if (r === UserRole.ADMIN || r === 'ADMIN') return UserRole.ADMIN;
    if (r === UserRole.SUPER_ADMIN || r === 'SUPER_ADMIN') return UserRole.SUPER_ADMIN;
    return UserRole.STUDENT;
};

// ---- DTO -> camelCase mapper -----------------------------------------------

const toSupportTicket = (row: SupportTicketRow): SupportTicket => {
    const meta = row.meta_data ?? undefined;
    return {
        id: row.id,
        userId: row.user_id,
        userRole: fromBackendRole(meta),
        userEmail: row.user_email ?? '',
        userName: row.user_name ?? '',
        category: fromBackendCategory(row.category, meta),
        subject: row.subject,
        description: row.message,
        status: (row.status as TicketStatus) || 'OPEN',
        priority: (row.priority as TicketPriority) || 'MEDIUM',
        createdAt: row.created_at,
        updatedAt: row.updated_at,
        metaData: meta as SupportTicket['metaData'],
        adminResponse: row.admin_response ?? undefined,
    };
};

// ---- Service ---------------------------------------------------------------

export const supportService = {
    /**
     * Create a new support ticket.
     * Accepts the same camelCase Partial<SupportTicket> shape the existing
     * components have been passing to the mock, translates fields to the
     * backend's snake_case wire format, and returns a fully populated
     * SupportTicket (camelCase) so callers can use the return value
     * directly (Support.tsx passes it to onTicketCreate).
     */
    createTicket: async (ticket: Partial<SupportTicket>): Promise<SupportTicket> => {
        // Preserve the frontend's richer category union + the user role
        // by stashing them in meta_data so we can restore them on read.
        const meta: Record<string, any> = { ...(ticket.metaData || {}) };
        if (ticket.category) {
            meta.originalCategory = ticket.category;
        }
        if (ticket.userRole) {
            meta.userRole = ticket.userRole;
        }

        const body = {
            subject: ticket.subject || 'Support Request',
            message: ticket.description || '',
            category: toBackendCategory(ticket.category),
            // No explicit priority from current callers -> backend defaults to MEDIUM.
            meta_data: meta,
        };

        const res = await api.post<SupportTicketRow>('/api/support/tickets', body);
        return toSupportTicket(res.data);
    },

    /**
     * List the current user's own tickets. Optionally filter by status.
     */
    getMyTickets: async (status?: TicketStatus): Promise<SupportTicket[]> => {
        const res = await api.get<SupportTicketRow[]>('/api/support/my-tickets', {
            params: status ? { status } : undefined,
        });
        return res.data.map(toSupportTicket);
    },

    /**
     * Super-admin list of all tickets with optional filters.
     */
    getAllTickets: async (filters?: {
        status?: TicketStatus;
        priority?: TicketPriority;
        category?: SupportCategory;
        from?: string;
        to?: string;
    }): Promise<SupportTicket[]> => {
        const params: Record<string, string> = {};
        if (filters?.status) params.status = filters.status;
        if (filters?.priority) params.priority = filters.priority;
        if (filters?.category) params.category = toBackendCategory(filters.category);
        if (filters?.from) params.from = filters.from;
        if (filters?.to) params.to = filters.to;

        const res = await api.get<SupportTicketRow[]>('/api/support/tickets', {
            params: Object.keys(params).length ? params : undefined,
        });
        return res.data.map(toSupportTicket);
    },

    /**
     * Fetch a single ticket by id. Owner or super admin.
     */
    getTicketById: async (id: string): Promise<SupportTicket> => {
        const res = await api.get<SupportTicketRow>(`/api/support/tickets/${id}`);
        return toSupportTicket(res.data);
    },

    /**
     * Super-admin only: change a ticket's status. Optional admin_notes are
     * appended to admin_response by the backend (no dedicated column).
     */
    updateTicketStatus: async (
        ticketId: string,
        status: TicketStatus,
        adminNotes?: string,
    ): Promise<void> => {
        await api.patch<SupportTicketRow>(
            `/api/support/tickets/${ticketId}/status`,
            {
                status,
                ...(adminNotes ? { admin_notes: adminNotes } : {}),
            },
        );
    },

    /**
     * Super-admin only: set / overwrite the public admin response on a ticket.
     */
    updateTicketResponse: async (
        ticketId: string,
        response: string,
    ): Promise<SupportTicket> => {
        const res = await api.patch<SupportTicketRow>(
            `/api/support/tickets/${ticketId}/response`,
            { admin_response: response },
        );
        return toSupportTicket(res.data);
    },

    /**
     * Super-admin only: hard-delete a ticket.
     */
    deleteTicket: async (ticketId: string): Promise<void> => {
        await api.delete(`/api/support/tickets/${ticketId}`);
    },
};
