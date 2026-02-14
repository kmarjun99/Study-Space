import api from './api';

export interface Inquiry {
    id: string;
    accommodationId: string;
    studentId: string;
    ownerId: string;
    type: 'QUESTION' | 'VISIT';
    question: string;
    studentName: string;
    studentPhone?: string;
    preferredDate?: string;
    preferredTime?: string;
    reply?: string;
    status: 'PENDING' | 'REPLIED' | 'CLOSED';
    createdAt: string;
    repliedAt?: string;
    accommodationName?: string;
}

export interface CreateInquiryData {
    accommodationId: string;
    type?: 'QUESTION' | 'VISIT';
    question: string;
    studentName: string;
    studentPhone?: string;
    preferredDate?: string;
    preferredTime?: string;
}

const mapInquiryFromApi = (data: any): Inquiry => ({
    id: data.id,
    accommodationId: data.accommodation_id,
    studentId: data.student_id,
    ownerId: data.owner_id,
    type: data.type,
    question: data.question,
    studentName: data.student_name,
    studentPhone: data.student_phone,
    preferredDate: data.preferred_date,
    preferredTime: data.preferred_time,
    reply: data.reply,
    status: data.status,
    createdAt: data.created_at,
    repliedAt: data.replied_at,
    accommodationName: data.accommodation_name
});

export const inquiryService = {
    // Create a new inquiry (question or visit request)
    createInquiry: async (data: CreateInquiryData): Promise<Inquiry> => {
        const response = await api.post('/inquiries/', {
            accommodation_id: data.accommodationId,
            type: data.type || 'QUESTION',
            question: data.question,
            student_name: data.studentName,
            student_phone: data.studentPhone,
            preferred_date: data.preferredDate,
            preferred_time: data.preferredTime
        });
        return mapInquiryFromApi(response.data);
    },

    // Get inquiries sent by current user (student view)
    getMyInquiries: async (): Promise<Inquiry[]> => {
        const response = await api.get('/inquiries/my');
        return response.data.map(mapInquiryFromApi);
    },

    // Get inquiries received by current user (owner view)
    getReceivedInquiries: async (): Promise<Inquiry[]> => {
        const response = await api.get('/inquiries/received');
        return response.data.map(mapInquiryFromApi);
    },

    // Reply to an inquiry (owner only)
    replyToInquiry: async (inquiryId: string, reply: string): Promise<Inquiry> => {
        const response = await api.put(`/inquiries/${inquiryId}/reply`, { reply });
        return mapInquiryFromApi(response.data);
    },

    // Get count of pending inquiries (owner)
    getPendingCount: async (): Promise<number> => {
        const response = await api.get('/inquiries/count/pending');
        return response.data.count;
    }
};
