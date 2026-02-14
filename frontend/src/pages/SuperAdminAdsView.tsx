
import React, { useState, useEffect } from 'react';
import { Card, Button, Input, Badge } from '../components/UI';
import { Plus, Trash2, ExternalLink, Sparkles, AlertTriangle, Users } from 'lucide-react';
import { adService } from '../services/adService';
import { Ad } from '../types';

export const SuperAdminAdsView = () => {
    const [ads, setAds] = useState<Ad[]>([]);
    const [isCreatingAd, setIsCreatingAd] = useState(false);
    const [newAd, setNewAd] = useState<Partial<Ad>>({
        categoryId: '',
        targetAudience: 'STUDENT',
        ctaText: 'Learn More'
    });
    const [dragActive, setDragActive] = useState(false);
    const [urlWarning, setUrlWarning] = useState('');
    const [customCategory, setCustomCategory] = useState('');

    useEffect(() => {
        loadAds();
    }, []);

    const loadAds = async () => {
        try {
            const fetchedAds = await adService.getAllAds(true);
            setAds(fetchedAds);
        } catch (e) {
            console.error("Failed to load ads", e);
        }
    };

    const handleCreateAd = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const finalAd = {
                ...newAd,
                categoryId: newAd.categoryId === 'OTHER' ? customCategory : newAd.categoryId
            };

            await adService.createAd(finalAd);
            setIsCreatingAd(false);
            setNewAd({
                categoryId: '',
                targetAudience: 'STUDENT',
                ctaText: 'Learn More'
            });
            setCustomCategory(''); // Reset custom category
            loadAds();
            alert("Ad Campaign Created Successfully!");
        } catch (e) {
            alert("Failed to create ad");
        }
    };

    const handleDeleteAd = async (id: string) => {
        if (!confirm("Are you sure?")) return;
        try {
            await adService.deleteAd(id);
            loadAds();
        } catch (e) {
            alert("Failed to delete ad");
        }
    };

    // Drag and Drop Logic
    const handleDrag = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const file = e.dataTransfer.files[0];
            const objectUrl = URL.createObjectURL(file);
            setNewAd(prev => ({ ...prev, imageUrl: objectUrl }));
        }
    };

    const handleUrlChange = (val: string) => {
        setNewAd({ ...newAd, imageUrl: val });
        if (val && !val.startsWith('http')) {
            setUrlWarning('URL should start with http:// or https://');
        } else {
            setUrlWarning('');
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Ad Campaigns</h2>
                    <p className="text-gray-500">Manage promotional content across the platform.</p>
                </div>
                <Button onClick={() => setIsCreatingAd(true)}><Plus className="w-4 h-4 mr-2" /> Create Campaign</Button>
            </div>

            {isCreatingAd && (
                <Card className="p-6 bg-indigo-50/50 border border-indigo-100 shadow-md">
                    <h3 className="font-bold text-lg text-indigo-900 mb-6">Create New Campaign</h3>
                    <form onSubmit={handleCreateAd} className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="col-span-2">
                            <Input label="Campaign Title" value={newAd.title || ''} onChange={e => setNewAd({ ...newAd, title: e.target.value })} required placeholder="e.g. Summer Discount 2024" />
                        </div>
                        <div className="col-span-2">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                            <textarea
                                className="w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-3 border"
                                rows={3}
                                value={newAd.description || ''}
                                onChange={e => setNewAd({ ...newAd, description: e.target.value })}
                                required
                                placeholder="Ad copy text..."
                            />
                        </div>

                        {/* Drag & Drop Input */}
                        <div className="col-span-2 space-y-2">
                            <label className="block text-sm font-medium text-gray-700">Ad Banner Image</label>
                            <div
                                className={`relative border-2 border-dashed rounded-lg p-6 flex flex-col items-center justify-center text-center transition-colors
                                    ${dragActive ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 bg-white hover:border-indigo-400'}`}
                                onDragEnter={handleDrag}
                                onDragLeave={handleDrag}
                                onDragOver={handleDrag}
                                onDrop={handleDrop}
                            >
                                <div className="p-3 bg-indigo-50 text-indigo-600 rounded-full mb-3">
                                    <Sparkles className="w-6 h-6" />
                                </div>
                                <p className="text-sm text-gray-600 font-medium">
                                    Drag & drop your image here, or <span className="text-indigo-600 cursor-pointer hover:underline">browse</span>
                                </p>
                                <p className="text-xs text-gray-400 mt-1">Supports JPG, PNG (Max 5MB)</p>
                                <input
                                    type="file"
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                    accept="image/*"
                                    onChange={(e) => {
                                        if (e.target.files?.[0]) {
                                            setNewAd(prev => ({ ...prev, imageUrl: URL.createObjectURL(e.target.files![0]) }));
                                        }
                                    }}
                                />
                            </div>

                            <div className="relative">
                                <Input
                                    label=""
                                    value={newAd.imageUrl || ''}
                                    onChange={e => handleUrlChange(e.target.value)}
                                    placeholder="Or paste direct Image URL..."
                                    className="text-xs"
                                />
                                {urlWarning && (
                                    <div className="absolute right-3 top-3 text-red-500 text-xs flex items-center bg-white px-1">
                                        <AlertTriangle className="w-3 h-3 mr-1" /> {urlWarning}
                                    </div>
                                )}
                            </div>

                            {newAd.imageUrl && (
                                <div className="mt-4 relative group w-full h-48 bg-gray-100 rounded-md overflow-hidden border border-gray-200">
                                    <img
                                        src={newAd.imageUrl}
                                        alt="Preview"
                                        className="w-full h-full object-cover"
                                        onError={(e) => (e.currentTarget.src = 'https://placehold.co/600x400?text=Invalid+Image+URL')}
                                    />
                                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity text-white text-sm font-medium">
                                        Live Preview
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="col-span-2">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Target Destination</label>
                            <div className="flex gap-2">
                                <div className="relative flex-1">
                                    <Input
                                        label=""
                                        value={newAd.link || ''}
                                        onChange={e => setNewAd({ ...newAd, link: e.target.value })}
                                        required
                                        placeholder="https://..."
                                    />
                                </div>
                                {newAd.link && (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        className="mt-0"
                                        onClick={() => window.open(newAd.link, '_blank')}
                                        title="Test Link"
                                    >
                                        <ExternalLink className="w-4 h-4" />
                                    </Button>
                                )}
                            </div>
                        </div>

                        <Input label="CTA Button Text" value={newAd.ctaText || ''} onChange={e => setNewAd({ ...newAd, ctaText: e.target.value })} placeholder="e.g. Book Now" />

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                            <div className="space-y-2">
                                <select
                                    className="w-full border-gray-300 rounded-lg shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2.5 bg-white border"
                                    value={newAd.categoryId === 'EDUCATION' || newAd.categoryId === 'FOOD' || newAd.categoryId === 'TRANSPORT' || newAd.categoryId === 'LIFESTYLE' ? newAd.categoryId : (newAd.categoryId ? 'OTHER' : '')}
                                    onChange={e => {
                                        const val = e.target.value;
                                        if (val === 'OTHER') {
                                            setNewAd({ ...newAd, categoryId: '' }); // Clear distinct ID, ready for custom input? Or use a flag?
                                            // Better approach: Use a dedicated 'isOther' state or just deduce.
                                            // Actually, simpler: Set to 'OTHER' temporarily in UI state or just handle it.
                                            // Let's rely on checking if value is not in standard list.
                                            setNewAd({ ...newAd, categoryId: 'OTHER' });
                                        } else {
                                            setNewAd({ ...newAd, categoryId: val });
                                        }
                                    }}
                                >
                                    <option value="">Select Category</option>
                                    <option value="EDUCATION">Education</option>
                                    <option value="FOOD">Food</option>
                                    <option value="TRANSPORT">Transport</option>
                                    <option value="LIFESTYLE">Lifestyle</option>
                                    <option value="OTHER">Other (Add your own)</option>
                                </select>

                                {newAd.categoryId === 'OTHER' && (
                                    <Input
                                        label=""
                                        placeholder="Type your category..."
                                        required
                                        autoFocus
                                        value={customCategory}
                                        onChange={(e) => setCustomCategory(e.target.value)}
                                        className="mt-2"
                                    />
                                )}
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Target Audience</label>
                            <select className="w-full border-gray-300 rounded-lg shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2.5 bg-white border" value={newAd.targetAudience} onChange={e => setNewAd({ ...newAd, targetAudience: e.target.value as any })}>
                                <option value="STUDENT">Students Only</option>
                                <option value="ADMIN">Partners (Owners) Only</option>
                                <option value="ALL">All Users</option>
                            </select>
                        </div>

                        <div className="col-span-2 flex justify-end gap-3 mt-4 pt-4 border-t border-indigo-100">
                            <Button type="button" variant="ghost" onClick={() => setIsCreatingAd(false)}>Cancel</Button>
                            <Button type="submit" variant="primary">Launch Campaign</Button>
                        </div>
                    </form>
                </Card>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {ads.map(ad => (
                    <Card key={ad.id} className="p-0 overflow-hidden flex flex-col h-full group hover:shadow-lg transition-shadow">
                        <div className="h-40 overflow-hidden relative bg-gray-100">
                            <img src={ad.imageUrl} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" alt={ad.title} />
                            <div className="absolute top-2 right-2">
                                <Badge variant="info" className="bg-white/90 backdrop-blur-sm shadow-sm">{ad.category}</Badge>
                            </div>
                        </div>
                        <div className="p-5 flex-1 flex flex-col">
                            <div className="flex-1">
                                <h3 className="font-bold text-gray-900 line-clamp-1 text-lg mb-1">{ad.title}</h3>
                                <p className="text-sm text-gray-500 line-clamp-2">{ad.description}</p>
                            </div>

                            <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between items-center">
                                <div className="flex items-center gap-2 text-xs font-medium text-gray-500 bg-gray-50 px-2 py-1 rounded">
                                    <Users className="w-3 h-3" /> {ad.targetAudience}
                                </div>
                                <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-700 hover:bg-red-50 -mr-2" onClick={() => handleDeleteAd(ad.id)}>
                                    <Trash2 className="w-4 h-4" />
                                </Button>
                            </div>
                        </div>
                    </Card>
                ))}
            </div>
        </div>
    );
};
