
import React, { useState, useEffect } from 'react';
import { PlatformSettings } from '../types';
import { Card, Button, Input, Badge } from '../components/UI';
import { Save, AlertTriangle, ToggleLeft, ToggleRight, DollarSign, Globe, Lock, Sliders, Mail, Smartphone } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface SuperAdminSettingsProps {
    settings: PlatformSettings;
    onUpdateSettings: (newSettings: PlatformSettings) => void;
}

export const SuperAdminSettings: React.FC<SuperAdminSettingsProps> = ({ settings, onUpdateSettings }) => {
    const navigate = useNavigate();
    const [localSettings, setLocalSettings] = useState<PlatformSettings>(settings);
    const [hasChanges, setHasChanges] = useState(false);

    useEffect(() => {
        // Basic deep comparison (simplified)
        if (JSON.stringify(localSettings) !== JSON.stringify(settings)) {
            setHasChanges(true);
        } else {
            setHasChanges(false);
        }
    }, [localSettings, settings]);

    const handleSave = () => {
        if (!confirm('Are you sure you want to save these global changes? This will persist immediately.')) return;
        onUpdateSettings(localSettings);
        setHasChanges(false);
        alert('Settings saved successfully!');
    };

    const handleToggle = (path: string, value: boolean) => {
        const parts = path.split('.');
        setLocalSettings(prev => {
            const next = { ...prev };
            let current: any = next;
            for (let i = 0; i < parts.length - 1; i++) {
                current = current[parts[i]];
            }
            current[parts[parts.length - 1]] = value;
            return next;
        });
    };

    const handleChange = (path: string, value: any) => {
        const parts = path.split('.');
        setLocalSettings(prev => {
            const next = { ...prev };
            let current: any = next;
            for (let i = 0; i < parts.length - 1; i++) {
                current = current[parts[i]];
            }
            current[parts[parts.length - 1]] = value;
            return next;
        });
    }

    return (
        <div className="space-y-8 animate-in fade-in pb-10 max-w-5xl mx-auto p-6">
            <div className="flex justify-between items-center sticky top-0 bg-white/95 backdrop-blur z-20 py-4 border-b border-gray-100">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <Sliders className="w-6 h-6 text-indigo-600" /> Platform Settings
                    </h1>
                    <p className="text-gray-500">Configure core platform behavior.</p>
                </div>
                <div className="flex gap-3">
                    <Button variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
                    <Button
                        onClick={handleSave}
                        variant={hasChanges ? 'primary' : 'secondary'}
                        disabled={!hasChanges}
                        className="transition-all"
                    >
                        <Save className="w-4 h-4 mr-2" /> Save Changes
                    </Button>
                </div>
            </div>

            {/* A. Platform Configuration */}
            <Card className="p-6">
                <div className="flex items-start gap-4 mb-6">
                    <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
                        <Globe className="w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-gray-900">Platform Identity</h2>
                        <p className="text-sm text-gray-500">Essential branding and support contact info.</p>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Input label="Platform Name" value={localSettings.platformName} onChange={(e) => handleChange('platformName', e.target.value)} />
                    <Input label="Support Email" value={localSettings.supportEmail} onChange={(e) => handleChange('supportEmail', e.target.value)} icon={<Mail className="w-4 h-4" />} />
                    <Input label="Support Phone" value={localSettings.supportPhone} onChange={(e) => handleChange('supportPhone', e.target.value)} icon={<Smartphone className="w-4 h-4" />} />

                    <div className="col-span-2 p-4 bg-red-50 border border-red-100 rounded-lg flex items-center justify-between">
                        <div>
                            <h4 className="font-bold text-red-900 flex items-center gap-2">
                                <AlertTriangle className="w-4 h-4" /> Maintenance Mode
                            </h4>
                            <p className="text-xs text-red-700 mt-1">
                                When enabled, all booking functionalities will be disabled for users.
                            </p>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input type="checkbox" checked={localSettings.maintenanceMode} onChange={(e) => handleChange('maintenanceMode', e.target.checked)} className="sr-only peer" />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
                        </label>
                    </div>
                </div>
            </Card>

            {/* B. Feature Toggles */}
            <Card className="p-6">
                <div className="flex items-start gap-4 mb-6">
                    <div className="p-2 bg-blue-50 rounded-lg text-blue-600">
                        <Lock className="w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-gray-900">Feature Toggles</h2>
                        <p className="text-sm text-gray-500">Enable or disable specific platform modules.</p>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                        { key: 'features.featuredListings', label: 'Featured Listings' },
                        { key: 'features.reviews', label: 'User Reviews' },
                        { key: 'features.waitlist', label: 'Waitlist System' },
                        { key: 'features.newVenueRegistrations', label: 'Venue Registration' }
                    ].map(feat => (
                        <div key={feat.key} className="flex items-center justify-between p-3 border rounded-lg bg-gray-50/50">
                            <span className="text-sm font-medium text-gray-700">{feat.label}</span>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={getValue(localSettings, feat.key)}
                                    onChange={(e) => handleToggle(feat.key, e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                            </label>
                        </div>
                    ))}
                </div>
            </Card>

            {/* C. Payment & Subscription */}
            <Card className="p-6">
                <div className="flex items-start gap-4 mb-6">
                    <div className="p-2 bg-green-50 rounded-lg text-green-600">
                        <DollarSign className="w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-lg font-bold text-gray-900">Monetization & Limits</h2>
                        <p className="text-sm text-gray-500">Control subscription fees and operational limits.</p>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="col-span-1">
                        <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">Subs Status</label>
                        <div className="flex items-center justify-between p-3 border rounded-lg bg-gray-50/50">
                            <span className="text-sm font-medium text-gray-700">New Subscriptions</span>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={localSettings.payments.enableNewSubscriptions}
                                    onChange={(e) => handleToggle('payments.enableNewSubscriptions', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-green-600"></div>
                            </label>
                        </div>
                    </div>
                    <div className="col-span-1">
                        <Input
                            label="Featured Listing Price (₹)"
                            type="number"
                            value={localSettings.payments.featuredListingPrice}
                            onChange={(e) => handleChange('payments.featuredListingPrice', parseInt(e.target.value))}
                        />
                    </div>
                    <div className="col-span-1">
                        <Input
                            label="Venue Subs. Duration (Days)"
                            type="number"
                            value={localSettings.payments.venueSubscriptionDurationDays}
                            onChange={(e) => handleChange('payments.venueSubscriptionDurationDays', parseInt(e.target.value))}
                        />
                    </div>
                </div>
            </Card>

            {/* D/E. Misc */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="p-6">
                    <h3 className="font-bold text-gray-900 mb-4">Core Preferences</h3>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Date Format</label>
                            <select className="w-full border-gray-300 rounded-lg shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2.5 bg-white border"
                                value={localSettings.preferences.dateFormat}
                                onChange={(e) => handleChange('preferences.dateFormat', e.target.value)}>
                                <option value="DD/MM/YYYY">DD/MM/YYYY</option>
                                <option value="MM/DD/YYYY">MM/DD/YYYY</option>
                                <option value="YYYY-MM-DD">YYYY-MM-DD</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Global Currency</label>
                            <select className="w-full border-gray-300 rounded-lg shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2.5 bg-white border" disabled value="INR">
                                <option value="INR">Indian Rupee (₹)</option>
                            </select>
                        </div>
                    </div>
                </Card>

                <Card className="p-6">
                    <h3 className="font-bold text-gray-900 mb-4">Location Controls</h3>
                    <div className="space-y-4">
                        <div className="flex items-center justify-between p-3 border rounded-lg bg-gray-50/50">
                            <div>
                                <span className="block text-sm font-medium text-gray-700">City-Based Availability</span>
                                <span className="text-xs text-gray-500">Only show venues in active cities</span>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={localSettings.locations.cityBasedAvailability}
                                    onChange={(e) => handleToggle('locations.cityBasedAvailability', e.target.checked)}
                                    className="sr-only peer"
                                />
                                <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
                            </label>
                        </div>
                        <div className="p-3 bg-indigo-50 rounded border border-indigo-100 text-xs text-indigo-700">
                            Map configuration and API keys are managed in deployment secrets.
                        </div>
                    </div>
                </Card>
            </div>


        </div>
    );
};

// Helper for deep access
function getValue(obj: any, path: string) {
    return path.split('.').reduce((o, i) => o[i], obj);
}
