
import React, { useState } from 'react';
import { User } from '../types';
import { Card, Button, Badge, Modal, Input } from '../components/UI';
import { useNavigate } from 'react-router-dom';
import { LogOut, User as UserIcon, Settings, HelpCircle, Shield, Trash2, Database, RefreshCw, CheckCircle, Edit2, Mail, Phone } from 'lucide-react';
import { cacheService } from '../services/cacheService';

interface SuperAdminProfileProps {
    user: User;
    onUpdateUser: (data: Partial<User>) => void;
    onLogout: () => void;
}

const CACHE_SCOPES = [
    { id: 'users', name: 'User Cache', description: 'Dashboards, bookings, reviews' },
    { id: 'owners', name: 'Owner Cache', description: 'Venues, housing, payments, boosts' },
    { id: 'listings', name: 'Listings Cache', description: 'Reading rooms, accommodations' },
    { id: 'plans', name: 'Plans & Promotions', description: 'Boost plans, active promotions' },
    { id: 'ads', name: 'Ads & Featured', description: 'Ad campaigns, featured listings' },
    { id: 'trust', name: 'Trust & Safety', description: 'Flags, cases, reminders' },
    { id: 'payments', name: 'Payments', description: 'Transaction history, pending payments' }
];

export const SuperAdminProfile: React.FC<SuperAdminProfileProps> = ({ user, onUpdateUser, onLogout }) => {
    const navigate = useNavigate();
    const [isCacheModalOpen, setIsCacheModalOpen] = useState(false);
    const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
    const [clearAll, setClearAll] = useState(false);
    const [isClearing, setIsClearing] = useState(false);
    const [clearSuccess, setClearSuccess] = useState(false);
    const [isEditProfileOpen, setIsEditProfileOpen] = useState(false);
    const [formData, setFormData] = useState({
        name: user.name,
        phone: user.phone || '',
    });
    const [isLoading, setIsLoading] = useState(false);

    const handleToggleScope = (scopeId: string) => {
        setSelectedScopes(prev =>
            prev.includes(scopeId)
                ? prev.filter(s => s !== scopeId)
                : [...prev, scopeId]
        );
    };

    const handleToggleAll = () => {
        if (clearAll) {
            setClearAll(false);
            setSelectedScopes([]);
        } else {
            setClearAll(true);
            setSelectedScopes([]);
        }
    };

    const handleClearCache = async () => {
        const scopesToClear = clearAll ? ['all'] : selectedScopes;
        if (scopesToClear.length === 0) return;

        setIsClearing(true);
        try {
            await cacheService.clearCache(scopesToClear);
            setClearSuccess(true);
            setTimeout(() => {
                setIsCacheModalOpen(false);
                setClearSuccess(false);
                setSelectedScopes([]);
                setClearAll(false);
                // Soft reload
                window.location.reload();
            }, 2000);
        } catch (error: any) {
            console.error('Failed to clear cache:', error);
            const errorMessage = error?.response?.data?.detail || error?.message || 'Unknown error';
            alert(`Failed to clear cache: ${errorMessage}`);
        } finally {
            setIsClearing(false);
        }
    };


    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmitUpdate = (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);

        setTimeout(() => {
            onUpdateUser({
                name: formData.name,
                phone: formData.phone,
            });
            setIsLoading(false);
            setIsEditProfileOpen(false);
        }, 800);
    };

    const handleOpenModal = () => {
        setSelectedScopes([]);
        setClearAll(false);
        setClearSuccess(false);
        setIsCacheModalOpen(true);
    };

    return (
        <div className="max-w-3xl mx-auto space-y-6">
            <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>

            <Card className="p-6">
                <div className="flex items-start gap-4">
                    <div className="h-16 w-16 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600">
                        <UserIcon className="w-8 h-8" />
                    </div>
                    <div className="flex-1">
                        <h2 className="text-xl font-bold text-gray-900">{user.name}</h2>
                        <div className="text-gray-500 mb-2">{user.email}</div>
                        <Badge variant="warning">Super Admin</Badge>
                    </div>
                </div>
            </Card>

            {/* System Controls - Super Admin Only */}
            <Card className="p-0 overflow-hidden">
                <div className="p-4 bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-semibold flex items-center gap-2">
                    <Settings className="w-5 h-5" />
                    System Controls
                </div>
                <div className="p-4">
                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-red-100 rounded-lg">
                                <Trash2 className="w-5 h-5 text-red-600" />
                            </div>
                            <div>
                                <p className="font-medium text-gray-900">Clear Cache</p>
                                <p className="text-sm text-gray-500">Clear cached data to fix stale state issues</p>
                            </div>
                        </div>
                        <Button onClick={handleOpenModal} variant="outline" className="text-red-600 border-red-200 hover:bg-red-50">
                            Clear Cache
                        </Button>
                    </div>
                </div>
            </Card>

            <Card className="p-0 overflow-hidden">
                <div className="p-4 bg-gray-50 border-b border-gray-100 font-semibold text-gray-700">Account Actions</div>
                <div className="divide-y divide-gray-100">
                    <button
                        onClick={() => navigate('/super-admin/tickets')}
                        className="w-full text-left px-6 py-4 hover:bg-gray-50 flex items-center gap-3 transition-colors"
                    >
                        <HelpCircle className="w-5 h-5 text-gray-400" />
                        <span className="text-gray-700 font-medium">Support Tickets</span>
                    </button>
                    <button
                        onClick={() => navigate('/super-admin/settings')}
                        className="w-full text-left px-6 py-4 hover:bg-gray-50 flex items-center gap-3 transition-colors"
                    >
                        <Settings className="w-5 h-5 text-gray-400" />
                        <span className="text-gray-700 font-medium">Platform Settings</span>
                    </button>

                    <button
                        onClick={onLogout}
                        className="w-full text-left px-6 py-4 hover:bg-red-50 flex items-center gap-3 transition-colors text-red-600"
                    >
                        <LogOut className="w-5 h-5" />
                        <span className="font-medium">Sign Out</span>
                    </button>
                </div>
            </Card>

            {/* Clear Cache Modal */}
            <Modal
                isOpen={isCacheModalOpen}
                onClose={() => setIsCacheModalOpen(false)}
                title="Clear System Cache"
            >
                <div className="py-2">
                    {clearSuccess ? (
                        <div className="text-center py-8">
                            <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
                                <CheckCircle className="w-8 h-8 text-green-600" />
                            </div>
                            <h3 className="text-xl font-bold text-gray-900 mb-2">Cache Cleared!</h3>
                            <p className="text-gray-500">Changes may take a few seconds to reflect.</p>
                        </div>
                    ) : (
                        <>
                            <p className="text-gray-600 mb-4">
                                Clears cached data to ensure the platform reflects the latest state.
                            </p>

                            <div className="mb-4">
                                <label className="block text-sm font-medium text-gray-700 mb-3">Cache Scope</label>
                                <div className="space-y-2 max-h-64 overflow-y-auto">
                                    {CACHE_SCOPES.map(scope => (
                                        <label
                                            key={scope.id}
                                            className={`flex items-center p-3 rounded-lg border cursor-pointer transition-colors ${selectedScopes.includes(scope.id) && !clearAll
                                                ? 'border-indigo-500 bg-indigo-50'
                                                : 'border-gray-200 hover:bg-gray-50'
                                                } ${clearAll ? 'opacity-50' : ''}`}
                                        >
                                            <input
                                                type="checkbox"
                                                checked={selectedScopes.includes(scope.id)}
                                                onChange={() => handleToggleScope(scope.id)}
                                                disabled={clearAll}
                                                className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                                            />
                                            <div className="ml-3">
                                                <p className="font-medium text-gray-900">{scope.name}</p>
                                                <p className="text-sm text-gray-500">{scope.description}</p>
                                            </div>
                                        </label>
                                    ))}
                                </div>
                            </div>

                            <label className="flex items-center p-3 rounded-lg border-2 border-red-200 bg-red-50 cursor-pointer mb-4">
                                <input
                                    type="checkbox"
                                    checked={clearAll}
                                    onChange={handleToggleAll}
                                    className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
                                />
                                <div className="ml-3">
                                    <p className="font-bold text-red-700">Clear ALL (System-wide)</p>
                                    <p className="text-sm text-red-600">Clears all cache namespaces</p>
                                </div>
                            </label>

                            <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 mb-4">
                                <p className="text-sm text-amber-700">
                                    <strong>Note:</strong> This does NOT affect active transactions, bookings, or seat holds.
                                    Only read cache is cleared.
                                </p>
                            </div>


            {/* Edit Profile Modal */}
            <Modal
                isOpen={isEditProfileOpen}
                onClose={() => setIsEditProfileOpen(false)}
                title="Edit Profile"
            >
                <form onSubmit={handleSubmitUpdate} className="space-y-4 py-2">
                    <Input label="Full Name" name="name" value={formData.name} onChange={handleChange} />
                    <div className="relative">
                        <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                        <input className="w-full px-3 py-2 border border-gray-200 bg-gray-50 text-gray-500 rounded-lg" value={user.email} readOnly />
                        <Mail className="w-4 h-4 text-gray-400 absolute right-3 top-9" />
                    </div>
                    <Input label="Phone Number" name="phone" value={formData.phone} onChange={handleChange} placeholder="+91..." />

                    <div className="pt-4 flex gap-3">
                        <Button type="button" variant="ghost" className="flex-1" onClick={() => setIsEditProfileOpen(false)}>Cancel</Button>
                        <Button type="submit" className="flex-1" isLoading={isLoading}>Save Changes</Button>
                    </div>
                </form>
            </Modal>
                            <div className="flex gap-3 pt-2">
                                <Button
                                    variant="ghost"
                                    className="flex-1"
                                    onClick={() => setIsCacheModalOpen(false)}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    className="flex-1 bg-red-600 hover:bg-red-700"
                                    isLoading={isClearing}
                                    onClick={handleClearCache}
                                    disabled={!clearAll && selectedScopes.length === 0}
                                >
                                    <Trash2 className="w-4 h-4 mr-2" />
                                    Clear Selected Cache
                                </Button>
                            </div>
                        </>
                    )}
                </div>
            </Modal>
        </div>
    );
};
