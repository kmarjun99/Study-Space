
import React, { useState, useEffect } from 'react';
import { Card, Button, Badge } from '../components/UI';
import { SupportTicket, TicketStatus } from '../types';
import { supportService } from '../services/supportService';

// Interface not needed if tickets are fetched internally, but we can keep it empty or optional
export interface SuperAdminSupportManagerProps { }

export const SuperAdminSupportManager: React.FC<SuperAdminSupportManagerProps> = () => {
    const [tickets, setTickets] = useState<SupportTicket[]>([]);
    const [filterStatus, setFilterStatus] = useState<'ALL' | 'OPEN' | 'IN_PROGRESS' | 'RESOLVED'>('ALL');
    const [filterRole, setFilterRole] = useState<'ALL' | 'STUDENT' | 'ADMIN'>('ALL');
    const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null);
    const [adminNotes, setAdminNotes] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadTickets();
    }, []);

    const loadTickets = async () => {
        setLoading(true);
        try {
            const data = await supportService.getAllTickets();
            setTickets(data);
        } catch (error) {
            console.error("Failed to load tickets", error);
        } finally {
            setLoading(false);
        }
    };

    const filteredTickets = tickets.filter(t => {
        if (filterStatus !== 'ALL' && t.status !== filterStatus) return false;
        if (filterRole !== 'ALL' && t.userRole !== filterRole) return false;
        return true;
    }).sort((a, b) => {
        // Sort Open first, then by date
        const isOpenA = a.status === 'OPEN';
        const isOpenB = b.status === 'OPEN';
        if (isOpenA && !isOpenB) return -1;
        if (!isOpenA && isOpenB) return 1;
        return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
    });

    const handleUpdateStatus = async (ticketId: string, newStatus: TicketStatus) => {
        try {
            await supportService.updateTicketStatus(ticketId, newStatus, adminNotes);
            alert(`Ticket status updated to ${newStatus}`);
            loadTickets(); // Refresh
            if (selectedTicket) {
                setSelectedTicket(prev => prev ? { ...prev, status: newStatus } : null);
            }
        } catch (error) {
            console.error("Failed to update ticket", error);
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            {selectedTicket ? (
                <div>
                    <Button variant="ghost" onClick={() => setSelectedTicket(null)} className="mb-4">
                        ← Back to Tickets
                    </Button>
                    <Card className="p-6">
                        <div className="flex justify-between items-start mb-6 border-b border-gray-100 pb-4">
                            <div>
                                <h2 className="text-2xl font-bold text-gray-900 mb-2">Ticket #{selectedTicket.id}</h2>
                                <div className="flex gap-2">
                                    <Badge variant={selectedTicket.userRole === 'ADMIN' ? 'warning' : 'info'}>
                                        {selectedTicket.userRole === 'ADMIN' ? 'OWNER' : 'USER'}
                                    </Badge>
                                    <Badge variant={
                                        selectedTicket.status === 'OPEN' ? 'error' :
                                            selectedTicket.status === 'IN_PROGRESS' ? 'warning' : 'success'
                                    }>{selectedTicket.status}</Badge>
                                </div>
                            </div>
                            <div className="text-right text-sm text-gray-500">
                                <div>Created: {new Date(selectedTicket.createdAt).toLocaleString()}</div>
                                <div>Category: {selectedTicket.category}</div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <div className="md:col-span-2 space-y-6">
                                <div>
                                    <h3 className="font-semibold text-gray-900 mb-2">Subject</h3>
                                    <p className="text-lg">{selectedTicket.subject}</p>
                                </div>
                                <div>
                                    <h3 className="font-semibold text-gray-900 mb-2">Description</h3>
                                    <div className="bg-gray-50 p-4 rounded-lg border border-gray-100 min-h-[100px] text-gray-700 whitespace-pre-wrap">
                                        {selectedTicket.description}
                                    </div>
                                </div>
                                {selectedTicket.metaData && (
                                    <div>
                                        <h3 className="font-semibold text-gray-900 mb-2">Metadata</h3>
                                        <pre className="text-xs bg-gray-900 text-gray-100 p-3 rounded overflow-x-auto">
                                            {JSON.stringify(selectedTicket.metaData, null, 2)}
                                        </pre>
                                    </div>
                                )}
                            </div>

                            <div className="space-y-6">
                                <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                                    <h3 className="font-bold text-gray-900 mb-4 border-b pb-2">User Details</h3>
                                    <div className="space-y-3 text-sm">
                                        <div>
                                            <span className="text-gray-500 block text-xs uppercase">User ID</span>
                                            <span className="font-mono">{selectedTicket.userId}</span>
                                        </div>
                                        <div>
                                            <span className="text-gray-500 block text-xs uppercase">Role</span>
                                            <span>{selectedTicket.userRole}</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
                                    <h3 className="font-bold text-gray-900 mb-4 border-b pb-2">Admin Actions</h3>

                                    <div className="space-y-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-1">Resolution Notes</label>
                                            <textarea
                                                className="w-full border rounded-lg p-2 text-sm"
                                                rows={3}
                                                value={adminNotes}
                                                onChange={e => setAdminNotes(e.target.value)}
                                                placeholder="Add notes before resolving..."
                                            />
                                        </div>

                                        <div className="grid grid-cols-1 gap-2">
                                            {selectedTicket.status !== 'IN_PROGRESS' && (
                                                <Button size="sm" variant="outline" onClick={() => handleUpdateStatus(selectedTicket.id, 'IN_PROGRESS')}>
                                                    Mark In Progress
                                                </Button>
                                            )}
                                            {selectedTicket.status !== 'RESOLVED' && (
                                                <Button size="sm" variant="primary" onClick={() => handleUpdateStatus(selectedTicket.id, 'RESOLVED')}>
                                                    Resolve Ticket
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </Card>
                </div>
            ) : (
                <div className="space-y-6">
                    <div className="flex justify-between items-center">
                        <div>
                            <h2 className="text-2xl font-bold text-gray-900">Support Tickets</h2>
                            <p className="text-gray-500">Manage user inquiries and issues.</p>
                        </div>
                        <Button variant="outline" onClick={loadTickets} isLoading={loading}>Refresh</Button>
                    </div>

                    <Card className="p-4 flex flex-wrap gap-4 items-center bg-gray-50">
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-700">Status:</span>
                            <select
                                className="border rounded-md p-1 text-sm"
                                value={filterStatus}
                                onChange={(e: any) => setFilterStatus(e.target.value)}
                            >
                                <option value="ALL">All Status</option>
                                <option value="OPEN">Open</option>
                                <option value="IN_PROGRESS">In Progress</option>
                                <option value="RESOLVED">Resolved</option>
                            </select>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-700">Role:</span>
                            <select
                                className="border rounded-md p-1 text-sm"
                                value={filterRole}
                                onChange={(e: any) => setFilterRole(e.target.value)}
                            >
                                <option value="ALL">All Roles</option>
                                <option value="STUDENT">Student</option>
                                <option value="ADMIN">Owner</option>
                            </select>
                        </div>
                    </Card>

                    <div className="space-y-4">
                        {filteredTickets.map(ticket => (
                            <Card key={ticket.id} className="p-4 hover:shadow-md transition-all cursor-pointer border-l-4 border-l-transparent hover:border-l-indigo-500" onClick={() => setSelectedTicket(ticket)}>
                                <div className="flex justify-between items-start">
                                    <div>
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="font-bold text-gray-900">{ticket.subject}</span>
                                            <Badge variant={ticket.status === 'OPEN' ? 'error' : ticket.status === 'IN_PROGRESS' ? 'warning' : 'success'}>
                                                {ticket.status}
                                            </Badge>
                                        </div>
                                        <p className="text-sm text-gray-500 line-clamp-1">{ticket.description}</p>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-xs text-gray-400">{new Date(ticket.createdAt).toLocaleDateString()}</div>
                                        <Badge variant="info" className="mt-1">{ticket.category}</Badge>
                                    </div>
                                </div>
                            </Card>
                        ))}
                        {filteredTickets.length === 0 && !loading && (
                            <div className="text-center py-12 text-gray-400">No tickets found matching filters.</div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};
