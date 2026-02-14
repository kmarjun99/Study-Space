
import React, { useState } from 'react';
import { User, SupportTicket, SupportCategory } from '../types';
import { Card, Button, Input, Badge } from '../components/UI';

import {
    MessageSquare, CheckCircle, Clock
} from 'lucide-react';
import { supportService } from '../services/supportService';

interface SupportProps {
    user: User;
    tickets: SupportTicket[];
    onTicketCreate: (ticket: SupportTicket) => void;
}

export const SupportPage: React.FC<SupportProps> = ({ user, tickets, onTicketCreate }) => {
    // Default to CREATE_TICKET view for "Single Support Screen" feel
    const [view, setView] = useState<'CREATE_TICKET' | 'MY_TICKETS'>('CREATE_TICKET');

    // Form State
    const [selectedCategory, setSelectedCategory] = useState<SupportCategory>('BOOKING_ISSUE');
    const [description, setDescription] = useState(''); // "Message Box"

    // We can keep subject for internal data structure but maybe hide it or auto-fill for simple UI?
    // User requested "Message Box (Free text)" only essentially? 
    // "B. Message Box Free text (mandatory)"
    // I'll keep Subject as an optional or auto-generated field if not explicitly requested, 
    // BUT usually a subject line is good practice. The requirements didn't EXPLICITLY forbid Subject, 
    // but listed "A. Issue Type, B. Message Box, C. Submit".
    // I will simplify by making Subject derived or a simple Input if needed. 
    // Let's keep a simple subject field labeled "Subject" or "Brief Summary" to be safe, 
    // or just use the first few words of description.
    // Actually, "Subject" was field previously. I'll keep it but perhaps make it secondary or part of the "Simple" form.
    // Wait, the requirement says "B. Message Box Free text (mandatory)". It doesn't mention Subject. 
    // I'll add a "Subject" field to be safe, or just merge it? Better to have it.
    const [subject, setSubject] = useState('');

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const myTickets = tickets.filter(t => t.userId === user.id).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

    const ISSUE_TYPES: { id: SupportCategory; label: string }[] = user.role === 'ADMIN' ? [
        { id: 'VENUE_ISSUE', label: 'Venue Listing Issue' },
        { id: 'SUBSCRIPTION', label: 'Subscription / Payment Issue' },
        { id: 'CABIN_MANAGEMENT', label: 'Cabin Management Issue' },
        { id: 'FEATURED_LISTING', label: 'Featured Listing Issue' },
        { id: 'TECHNICAL_ISSUE', label: 'Technical Issue' },
        { id: 'GENERAL_HELP', label: 'General Help' }
    ] : [
        { id: 'BOOKING_ISSUE', label: 'Booking Issue' },
        { id: 'PAYMENT_ISSUE', label: 'Payment Issue' },
        { id: 'TECHNICAL_ISSUE', label: 'Technical Issue' },
        { id: 'GENERAL_HELP', label: 'General Help' }
    ];

    // Reset category if not valid for role
    React.useEffect(() => {
        if (!ISSUE_TYPES.find(t => t.id === selectedCategory)) {
            setSelectedCategory(ISSUE_TYPES[0].id);
        }
    }, [user.role]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!description || !selectedCategory) return;

        setIsSubmitting(true);
        try {
            const metaData: any = {
                deviceInfo: navigator.userAgent,
                appVersion: '1.0.0'
            };
            if (user.role === 'ADMIN') {
                metaData.ownerId = user.id;
            }

            const newTicket = await supportService.createTicket({
                userId: user.id,
                userRole: user.role,
                userEmail: user.email,
                userName: user.name,
                category: selectedCategory,
                subject: subject || `${ISSUE_TYPES.find(t => t.id === selectedCategory)?.label} - ${new Date().toLocaleDateString()}`,
                description,
                metaData
            });
            onTicketCreate(newTicket);
            setSuccessMessage("Your request has been submitted. Our support team will contact you shortly.");
            setSubject('');
            setDescription('');
            // Optional: Auto-switch to My Tickets or just show success? 
            // "D. Success State Show confirmation: 'Your request...'"
        } catch (err) {
            console.error(err);
            alert("Failed to submit ticket. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'OPEN': return 'bg-blue-100 text-blue-700';
            case 'RESOLVED': return 'bg-green-100 text-green-700';
            case 'CLOSED': return 'bg-gray-100 text-gray-700';
            default: return 'bg-yellow-100 text-yellow-700';
        }
    };

    return (
        <div className="max-w-3xl mx-auto p-4 md:p-8 space-y-6">
            <div className="flex justify-between items-center">
                <h1 className="text-2xl font-bold text-gray-900">Support Center</h1>
                {view === 'CREATE_TICKET' ? (
                    <Button variant="ghost" onClick={() => { setView('MY_TICKETS'); setSuccessMessage(null); }}>View My Tickets</Button>
                ) : (
                    <Button variant="ghost" onClick={() => setView('CREATE_TICKET')}>Contact Support</Button>
                )}
            </div>

            {view === 'CREATE_TICKET' && (
                <Card className="p-6 md:p-8">
                    {successMessage ? (
                        <div className="text-center py-8">
                            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100 mb-4">
                                <CheckCircle className="h-6 w-6 text-green-600" />
                            </div>
                            <h3 className="text-lg font-medium text-gray-900">Request Submitted</h3>
                            <p className="mt-2 text-sm text-gray-500">{successMessage}</p>
                            <div className="mt-6">
                                <Button onClick={() => { setSuccessMessage(null); setView('MY_TICKETS'); }}>View Ticket Status</Button>
                            </div>
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit} className="space-y-6">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">Issue Type</label>
                                <select
                                    className="w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 py-2.5 px-3 border"
                                    value={selectedCategory}
                                    onChange={(e) => setSelectedCategory(e.target.value as SupportCategory)}
                                >
                                    {ISSUE_TYPES.map(type => (
                                        <option key={type.id} value={type.id}>{type.label}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Optional Subject Field - Keeping it for better data quality but making it look secondary or standard */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">Subject (Optional)</label>
                                <Input
                                    value={subject}
                                    onChange={(e) => setSubject(e.target.value)}
                                    placeholder="Brief summary of the issue"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">Message</label>
                                <textarea
                                    className="w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 min-h-[150px] p-3 border"
                                    value={description}
                                    onChange={e => setDescription(e.target.value)}
                                    placeholder="Describe your issue in detail..."
                                    required
                                />
                            </div>

                            <Button
                                type="submit"
                                className="w-full"
                                disabled={!description.trim() || isSubmitting}
                                isLoading={isSubmitting}
                            >
                                Submit Request
                            </Button>
                        </form>
                    )}
                </Card>
            )}

            {view === 'MY_TICKETS' && (
                <div className="space-y-4">
                    {myTickets.length === 0 ? (
                        <div className="text-center py-12 bg-gray-50 rounded-xl border border-dashed border-gray-300">
                            <p className="text-gray-500">No support tickets found.</p>
                        </div>
                    ) : (
                        myTickets.map(ticket => (
                            <Card key={ticket.id} className="p-5">
                                <div className="flex justify-between items-start mb-2">
                                    <h3 className="font-semibold text-gray-900">{ticket.subject}</h3>
                                    <Badge className={getStatusColor(ticket.status)}>{ticket.status.replace(/_/g, ' ')}</Badge>
                                </div>
                                <p className="text-sm text-gray-600 mb-3">{ticket.description}</p>
                                <div className="flex items-center gap-4 text-xs text-gray-400">
                                    <span className="flex items-center"><Clock className="w-3 h-3 mr-1" /> {new Date(ticket.createdAt).toLocaleDateString()}</span>
                                    <span>Category: {ISSUE_TYPES.find(t => t.id === ticket.category)?.label || ticket.category}</span>
                                </div>
                                {ticket.adminResponse && (
                                    <div className="mt-3 pt-3 border-t border-gray-100 bg-gray-50 p-3 rounded text-sm">
                                        <span className="font-semibold text-indigo-700 block mb-1">Support Response:</span>
                                        {ticket.adminResponse}
                                    </div>
                                )}
                            </Card>
                        ))
                    )}
                </div>
            )}
        </div>
    );
};
