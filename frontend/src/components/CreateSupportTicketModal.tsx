
import React, { useState } from 'react';
import { Button, Input } from './UI';
import { supportService } from '../services/supportService';
import { User, SupportCategory } from '../types';
import { X, MessageSquare } from 'lucide-react';

interface CreateSupportTicketModalProps {
    isOpen: boolean;
    onClose: () => void;
    user: User;
    initialSubject?: string;
    initialDescription?: string;
    category?: SupportCategory;
}

export const CreateSupportTicketModal: React.FC<CreateSupportTicketModalProps> = ({
    isOpen,
    onClose,
    user,
    initialSubject = '',
    initialDescription = '',
    category = 'GENERAL_HELP'
}) => {
    const [subject, setSubject] = useState(initialSubject);
    const [description, setDescription] = useState(initialDescription);
    const [selectedCategory, setSelectedCategory] = useState<SupportCategory>(category);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    // Reset state when opening with new props
    React.useEffect(() => {
        if (isOpen) {
            setSubject(initialSubject);
            setDescription(initialDescription);
            setSelectedCategory(category);
            setErrorMessage(null);
        }
    }, [isOpen, initialSubject, initialDescription, category]);

    if (!isOpen) return null;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (isSubmitting) return;
        setIsSubmitting(true);
        setErrorMessage(null);
        try {
            await supportService.createTicket({
                userId: user.id,
                userRole: user.role,
                userEmail: user.email,
                userName: user.name,
                category: selectedCategory,
                subject,
                description,
                metaData: { source: 'AdminDashboard' }
            });
            alert("Support ticket created successfully.");
            onClose();
        } catch (error: any) {
            console.error(error);
            const detail = error?.response?.data?.detail || error?.message;
            setErrorMessage(
                typeof detail === 'string' && detail
                    ? `Failed to create ticket: ${detail}`
                    : 'Failed to create ticket. Please try again.'
            );
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
                    <div className="bg-indigo-100 p-2 rounded-lg text-indigo-600">
                        <MessageSquare className="w-6 h-6" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">Contact Support</h2>
                        <p className="text-sm text-gray-500">We're here to help with your issue.</p>
                    </div>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                        <Input
                            value={subject}
                            onChange={(e) => setSubject(e.target.value)}
                            required
                            placeholder="Brief summary of the issue"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                        <textarea
                            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-3 border min-h-[120px]"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            required
                            placeholder="Please provide details about your issue..."
                        />
                    </div>

                    {errorMessage && (
                        <div
                            role="alert"
                            className="rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm p-3"
                        >
                            {errorMessage}
                        </div>
                    )}

                    <div className="pt-2 flex justify-end gap-3">
                        <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
                        <Button type="submit" isLoading={isSubmitting} disabled={isSubmitting}>Submit Ticket</Button>
                    </div>
                </form>
            </div>
        </div>
    );
};
