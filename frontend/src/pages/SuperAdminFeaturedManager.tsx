
import React, { useState } from 'react';
import { ReadingRoom, Accommodation, User } from '../types';
import { Card, Button, Badge } from '../components/UI';

interface SuperAdminFeaturedManagerProps {
    readingRooms: ReadingRoom[];
    accommodations: Accommodation[];
    users: User[];
}

export const SuperAdminFeaturedManager: React.FC<SuperAdminFeaturedManagerProps> = ({ readingRooms, accommodations, users }) => {
    const [activeTab, setActiveTab] = useState<'REQUESTS' | 'ACTIVE' | 'HISTORY'>('REQUESTS');

    // Combine Venues and PGs
    const allListings = [
        ...readingRooms.map(r => ({ ...r, entityType: 'VENUE' })),
        ...accommodations.map(a => ({ ...a, entityType: 'PG' }))
    ];

    // Logic: Request = Plan set but not active (false/undefined isFeatured)
    // Logic: Active = Plan set + isFeatured true + not expired
    // Logic: Expired/History = isFeatured true + expired

    const featuredRequests = allListings.filter(l => l.featuredPlan && !l.isFeatured);
    const activeFeatured = allListings.filter(l => l.isFeatured && (!l.featuredExpiry || new Date(l.featuredExpiry) > new Date()));
    const expiredFeatured = allListings.filter(l => l.isFeatured && l.featuredExpiry && new Date(l.featuredExpiry) <= new Date());

    const displayItems = activeTab === 'REQUESTS' ? featuredRequests
        : activeTab === 'ACTIVE' ? activeFeatured
            : expiredFeatured;

    const handleAction = (id: string, type: string, action: 'APPROVE' | 'REJECT' | 'SUSPEND') => {
        if (confirm(`Confirm ${action} for this listing?`)) {
            // In a real app, this would call API endpoints like /api/admin/featured/{id}/{action}
            // For now, we simulate the success feedback.
            alert(`${action} successful! The listing status has been updated.`);
            // Since we don't have dispatch here, we rely on page refresh or parent update in real app.
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Featured Listings</h2>
                    <p className="text-gray-500">Approve and manage promoted venues.</p>
                </div>
                <div className="flex gap-2">
                    <Button variant={activeTab === 'REQUESTS' ? 'primary' : 'outline'} onClick={() => setActiveTab('REQUESTS')}>
                        Requests <Badge variant={activeTab === 'REQUESTS' ? 'info' : 'warning'} className="ml-2">{featuredRequests.length}</Badge>
                    </Button>
                    <Button variant={activeTab === 'ACTIVE' ? 'primary' : 'outline'} onClick={() => setActiveTab('ACTIVE')}>
                        Active <Badge variant={activeTab === 'ACTIVE' ? 'info' : 'success'} className="ml-2">{activeFeatured.length}</Badge>
                    </Button>
                    <Button variant={activeTab === 'HISTORY' ? 'primary' : 'outline'} onClick={() => setActiveTab('HISTORY')}>
                        History
                    </Button>
                </div>
            </div>

            <Card className="p-0 overflow-hidden border border-gray-200 shadow-sm">
                <table className="w-full text-left text-sm text-gray-500">
                    <thead className="bg-gray-50 text-xs uppercase text-gray-700 font-semibold border-b">
                        <tr>
                            <th className="px-6 py-4">Listing</th>
                            <th className="px-6 py-4">Owner</th>
                            <th className="px-6 py-4">Plan Duration</th>
                            <th className="px-6 py-4">Payment</th>
                            <th className="px-6 py-4 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {displayItems.length === 0 ? (
                            <tr><td colSpan={5} className="px-6 py-12 text-center text-gray-400">No listings found in this category.</td></tr>
                        ) : displayItems.map(item => {
                            const owner = users.find(u => u.id === item.ownerId);
                            return (
                                <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                                    <td className="px-6 py-4">
                                        <div className="font-bold text-gray-900">{item.name}</div>
                                        <Badge variant="info" className="mt-1">{item.entityType}</Badge>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="text-gray-900 font-medium">{owner?.name || 'Unknown'}</div>
                                        <div className="text-xs text-gray-500">{owner?.email}</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className="font-semibold text-indigo-600 block">{item.featuredPlan}</span>
                                        {item.featuredExpiry && <span className="text-xs text-gray-400">Exp: {item.featuredExpiry}</span>}
                                    </td>
                                    <td className="px-6 py-4">
                                        {/* Assuming payment is pre-verified or handled via gateway callback before appearing here */}
                                        <Badge variant="success">PAID</Badge>
                                    </td>
                                    <td className="px-6 py-4 text-right space-x-2">
                                        {activeTab === 'REQUESTS' && (
                                            <>
                                                <Button size="sm" variant="primary" onClick={() => handleAction(item.id, item.entityType as string, 'APPROVE')}>Approve</Button>
                                                <Button size="sm" variant="danger" onClick={() => handleAction(item.id, item.entityType as string, 'REJECT')}>Reject</Button>
                                            </>
                                        )}
                                        {activeTab === 'ACTIVE' && (
                                            <Button size="sm" variant="ghost" className="text-red-600 hover:bg-red-50" onClick={() => handleAction(item.id, item.entityType as string, 'SUSPEND')}>Disable</Button>
                                        )}
                                        {activeTab === 'HISTORY' && (
                                            <span className="text-xs text-gray-400 italic">Expired</span>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </Card>
        </div>
    );
};
