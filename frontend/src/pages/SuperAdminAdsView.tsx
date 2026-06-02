
import React, { useState, useEffect } from 'react';
import { Card, Button, Input, Badge } from '../components/UI';
import { Plus, Trash2, ExternalLink, Sparkles, AlertTriangle, Users } from 'lucide-react';
import { adService } from '../services/adService';
import { Ad, AdCategoryEntity } from '../types';
import { imageUrl } from '../utils/imageUtils';

export const SuperAdminAdsView = () => {
    const [ads, setAds] = useState<Ad[]>([]);
    const [categories, setCategories] = useState<AdCategoryEntity[]>([]);
    const [isCreatingAd, setIsCreatingAd] = useState(false);
    const [newAd, setNewAd] = useState<Partial<Ad>>({
        categoryId: '',
        targetAudience: 'STUDENT',
        ctaText: 'Learn More'
    });
    const [urlWarning, setUrlWarning] = useState('');
    const [isFixingBlobs, setIsFixingBlobs] = useState(false);

    useEffect(() => {
        loadAds();
        loadCategories();
    }, []);

    const loadCategories = async () => {
        try {
            const fetchedCategories = await adService.getCategories();
            setCategories(fetchedCategories);
        } catch (e) {
            console.error("Failed to load categories", e);
        }
    };

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
        
        // Validate image URL is not a blob URL
        if (newAd.imageUrl && newAd.imageUrl.startsWith('blob:')) {
            alert("❌ File upload detected! Please use a direct image URL instead.\n\nUpload your image to:\n• Imgur.com\n• Cloudinary.com\n• Or use Unsplash image URLs");
            return;
        }
        
        // Validate image URL starts with http/https
        if (newAd.imageUrl && !newAd.imageUrl.startsWith('http://') && !newAd.imageUrl.startsWith('https://')) {
            alert("❌ Invalid image URL. Must start with http:// or https://");
            return;
        }
        
        try {
            await adService.createAd(newAd);
            setIsCreatingAd(false);
            setNewAd({
                categoryId: '',
                targetAudience: 'STUDENT',
                ctaText: 'Learn More'
            });
            loadAds();
            alert("Ad Campaign Created Successfully!");
        } catch (e) {
            console.error("Error creating ad:", e);
            alert("Failed to create ad. Please try again.");
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

    const getCategoryName = (categoryId?: string): string => {
        if (!categoryId) return 'No Category';
        const category = categories.find(c => c.id === categoryId);
        return category?.name || categoryId;
    };

    const handleUrlChange = (val: string) => {
        setNewAd({ ...newAd, imageUrl: val });
        if (val && val.startsWith('blob:')) {
            setUrlWarning('❌ Blob URLs are not supported. Use a direct image URL.');
        } else if (val && !val.startsWith('http://') && !val.startsWith('https://')) {
            setUrlWarning('URL must start with http:// or https://');
        } else {
            setUrlWarning('');
        }
    };

    const handleFixBlobUrls = async () => {
        const blobAds = ads.filter(ad => ad.imageUrl && ad.imageUrl.startsWith('blob:'));
        
        if (blobAds.length === 0) {
            alert('✅ No ads with blob URLs found!');
            return;
        }

        const confirmed = confirm(
            `Found ${blobAds.length} ad(s) with invalid blob URLs:\n\n` +
            blobAds.map(ad => `• ${ad.title}`).join('\n') +
            `\n\nThese will be replaced with a placeholder image. Continue?`
        );

        if (!confirmed) return;

        setIsFixingBlobs(true);
        try {
            const response = await adService.fixBlobUrls();
            alert(
                `✅ ${response.message}\n\n` +
                `Fixed ${response.fixed_count} ad(s).\n\n` +
                `Next steps:\n` +
                `1. Refresh the page\n` +
                `2. Edit each ad and add proper image URLs from Imgur or Unsplash`
            );
            loadAds(); // Reload ads to show updated images
        } catch (e) {
            console.error('Failed to fix blob URLs:', e);
            alert('❌ Failed to fix blob URLs. Please try again.');
        } finally {
            setIsFixingBlobs(false);
        }
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Ad Campaigns</h2>
                    <p className="text-gray-500">Manage promotional content across the platform.</p>
                </div>
                <div className="flex gap-2">
                    {ads.some(ad => ad.imageUrl && ad.imageUrl.startsWith('blob:')) && (
                        <Button 
                            variant="outline" 
                            onClick={handleFixBlobUrls}
                            disabled={isFixingBlobs}
                            className="border-amber-300 text-amber-700 hover:bg-amber-50"
                        >
                            <AlertTriangle className="w-4 h-4 mr-2" />
                            {isFixingBlobs ? 'Fixing...' : 'Fix Broken Images'}
                        </Button>
                    )}
                    <Button onClick={() => setIsCreatingAd(true)}>
                        <Plus className="w-4 h-4 mr-2" /> Create Campaign
                    </Button>
                </div>
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

                        {/* Image URL Input */}
                        <div className="col-span-2 space-y-2">
                            <label className="block text-sm font-medium text-gray-700">Ad Banner Image URL</label>
                            
                            {/* Instructions Box */}
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-3">
                                <div className="flex items-start gap-2">
                                    <Sparkles className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
                                    <div className="text-sm text-blue-900">
                                        <p className="font-semibold mb-2">How to add an image:</p>
                                        <ol className="list-decimal list-inside space-y-1 text-xs">
                                            <li>Upload your image to <a href="https://imgur.com/upload" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline font-medium">Imgur.com</a> or <a href="https://cloudinary.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline font-medium">Cloudinary.com</a></li>
                                            <li>Copy the direct image URL (must end in .jpg, .png, or .webp)</li>
                                            <li>Paste it in the field below</li>
                                            <li>Or use free images from <a href="https://unsplash.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline font-medium">Unsplash.com</a></li>
                                        </ol>
                                    </div>
                                </div>
                            </div>

                            <div className="relative">
                                <Input
                                    label=""
                                    value={newAd.imageUrl || ''}
                                    onChange={e => handleUrlChange(e.target.value)}
                                    placeholder="https://i.imgur.com/example.jpg or https://images.unsplash.com/..."
                                    required
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
                            <label className="block text-sm font-medium text-gray-700 mb-1">Category (Optional)</label>
                            <select
                                className="w-full border-gray-300 rounded-lg shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2.5 bg-white border"
                                value={newAd.categoryId || ''}
                                onChange={e => setNewAd({ ...newAd, categoryId: e.target.value })}
                            >
                                <option value="">No Category</option>
                                {categories.length === 0 ? (
                                    <option disabled>Loading categories...</option>
                                ) : (
                                    categories.map(cat => (
                                        <option key={cat.id} value={cat.id}>
                                            {cat.name} ({cat.group})
                                        </option>
                                    ))
                                )}
                            </select>
                            {categories.length === 0 && (
                                <p className="text-xs text-amber-600 mt-1">
                                    <AlertTriangle className="w-3 h-3 inline mr-1" />
                                    Categories not loaded. Contact admin to seed categories.
                                </p>
                            )}
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
                            <img src={imageUrl(ad.imageUrl, { w: 480, fmt: 'webp' })} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" alt={ad.title} loading="lazy" decoding="async" />
                            {ad.categoryId && (
                                <div className="absolute top-2 right-2">
                                    <Badge variant="info" className="bg-white/90 backdrop-blur-sm shadow-sm">
                                        {getCategoryName(ad.categoryId)}
                                    </Badge>
                                </div>
                            )}
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
