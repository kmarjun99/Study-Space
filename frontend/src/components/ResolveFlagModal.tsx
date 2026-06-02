
import React, { useState } from 'react';
import { Button } from './UI';
import { trustService } from '../services/trustService';
import { User } from '../types';
import { X, CheckCircle, FileWarning } from 'lucide-react';

interface ResolveFlagModalProps {
    isOpen: boolean;
    onClose: () => void;
    flag: any; // Using any for now to match flag structure usage in dashboard
    user: User;
    onSuccess: () => void;
}

export const ResolveFlagModal: React.FC<ResolveFlagModalProps> = ({ isOpen, onClose, flag, user, onSuccess }) => {
    const [notes, setNotes] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    if (!isOpen || !flag) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            await trustService.ownerResubmit(
                flag.id,
                notes,
                user.id,
                user.name
            );
            alert("Resolution submitted successfully. Steps will be reviewed shortly.");
            onSuccess();
            onClose();
        } catch (error) {
            console.error(error);
            alert("Failed to submit resolution.");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 relative animate-in zoom-in-95 duration-200">
                <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600">
                    <X className="w-5 h-5" />
                </button>

                <div className="flex items-center gap-3 mb-6">
                    <div className="bg-orange-100 p-2 rounded-lg text-orange-600">
                        <FileWarning className="w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">Resolve Flag</h2>
                        <p className="text-sm text-gray-500">Address the issue for {flag.entity_name}</p>
                    </div>
                </div>

                <div className="mb-6 bg-gray-50 border border-gray-100 rounded-lg p-4">
                    <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Detailed Reason</h3>
                    <p className="text-gray-800 text-sm">
                        {flag.custom_reason || flag.flag_type?.replace(/_/g, ' ') || 'No specific reason provided.'}
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Resolution Actions Taken</label>
                        <textarea
                            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-3 border min-h-[120px]"
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            required
                            placeholder="Describe what changes you made to resolve this issue..."
                        />
                        <p className="text-xs text-gray-500 mt-1">This will be sent to the admin for review.</p>
                    </div>

                    <div className="pt-2 flex justify-end gap-3">
                        <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
                        <Button type="submit" isLoading={isSubmitting}>Submit for Review</Button>
                    </div>
                </form>
            </div>
        </div>
    );
};
