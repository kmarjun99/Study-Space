
import { SupportTicket, SupportCategory, TicketPriority, TicketStatus, UserRole } from '../types';

// In-memory mock data (persists during session)
let mockTickets: SupportTicket[] = [
    {
        id: 'ticket-1',
        userId: 'user-1',
        userRole: UserRole.STUDENT,
        userEmail: 'student@example.com',
        userName: 'John Student',
        category: 'PAYMENT_ISSUE',
        subject: 'Payment failed for booking',
        description: 'I tried to book cabin A1 but payment failed.',
        status: 'OPEN',
        priority: 'HIGH',
        createdAt: new Date(Date.now() - 86400000).toISOString(),
        updatedAt: new Date(Date.now() - 86400000).toISOString()
    },
    {
        id: 'ticket-2',
        userId: 'user-2',
        userRole: UserRole.ADMIN,
        userEmail: 'owner@example.com',
        userName: 'Jane Owner',
        category: 'TECHNICAL_ISSUE',
        subject: 'Cannot update venue details',
        description: 'Update button is disabled.',
        status: 'RESOLVED',
        priority: 'MEDIUM',
        createdAt: new Date(Date.now() - 172800000).toISOString(),
        updatedAt: new Date(Date.now() - 100000000).toISOString()
    }
];

export const supportService = {
    createTicket: async (ticket: Partial<SupportTicket>): Promise<SupportTicket> => {
        // Simulate API call
        return new Promise((resolve) => {
            setTimeout(() => {
                const newTicket: SupportTicket = {
                    id: `ticket-${Date.now()}`,
                    userId: ticket.userId!,
                    userRole: ticket.userRole!,
                    userEmail: ticket.userEmail!,
                    userName: ticket.userName!,
                    category: ticket.category || 'OTHER',
                    subject: ticket.subject || 'Support Request',
                    description: ticket.description || '',
                    status: 'OPEN',
                    priority: 'MEDIUM',
                    createdAt: new Date().toISOString(),
                    updatedAt: new Date().toISOString(),
                    metaData: ticket.metaData
                };
                mockTickets.unshift(newTicket);
                resolve(newTicket);
            }, 800);
        });
    },

    updateTicketStatus: async (ticketId: string, status: TicketStatus, adminNotes?: string): Promise<void> => {
        // Simulate API
        return new Promise((resolve) => {
            setTimeout(() => {
                mockTickets = mockTickets.map(t =>
                    t.id === ticketId
                        ? { ...t, status, adminNotes: adminNotes || t.adminNotes, updatedAt: new Date().toISOString() }
                        : t
                );
                resolve();
            }, 500);
        });
    },

    getAllTickets: async (): Promise<SupportTicket[]> => {
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve([...mockTickets]);
            }, 500);
        });
    }
};
