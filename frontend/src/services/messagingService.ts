import { Message, Conversation } from '../types';
import api from './api'; // Use centralized api instance with correct token

const API_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Transform backend snake_case to frontend camelCase
function transformMessage(backendMessage: any): Message {
  return {
    id: backendMessage.id,
    conversationId: backendMessage.conversation_id,
    senderId: backendMessage.sender_id,
    senderName: backendMessage.sender_name,
    senderRole: backendMessage.sender_role,
    receiverId: backendMessage.receiver_id,
    receiverName: backendMessage.receiver_name,
    receiverRole: backendMessage.receiver_role,
    content: backendMessage.content,
    timestamp: backendMessage.timestamp,
    read: backendMessage.read,
    venueId: backendMessage.venue_id,
    venueName: backendMessage.venue_name,
    venueType: backendMessage.venue_type,
  };
}

function transformConversation(backendConv: any): Conversation {
  return {
    id: backendConv.id,
    participantIds: backendConv.participant_ids || [],
    participants: backendConv.participants || [],
    lastMessage: backendConv.last_message ? transformMessage(backendConv.last_message) : undefined,
    unreadCount: backendConv.unread_count || 0,
    venueId: backendConv.venue_id,
    venueName: backendConv.venue_name,
    venueType: backendConv.venue_type,
  };
}

class MessagingService {
  // Get all conversations for current user
  async getConversations(): Promise<Conversation[]> {
    try {
      const response = await api.get(`/messages/conversations`);
      return response.data.map(transformConversation);
    } catch (error) {
      console.error('Failed to fetch conversations:', error);
      // Return empty for now if error, or throw? The previous code re-threw.
      // Keeping existing behavior
      throw error;
    }
  }

  // Get messages in a specific conversation
  async getMessages(conversationId: string): Promise<Message[]> {
    try {
      const response = await api.get(`/messages/conversations/${conversationId}/messages`);
      return response.data.map(transformMessage);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      throw error;
    }
  }

  // Send a message
  async sendMessage(receiverId: string, content: string, venueId?: string): Promise<Message> {
    try {
      const response = await api.post(`/messages/send`, {
        receiver_id: receiverId,
        content,
        venue_id: venueId,
      });
      return transformMessage(response.data);
    } catch (error) {
      console.error('Failed to send message:', error);
      throw error;
    }
  }

  // Mark message as read
  async markAsRead(messageId: string): Promise<void> {
    try {
      await api.put(`/messages/${messageId}/read`);
      window.dispatchEvent(new Event('messagesUpdated')); // Notify app to refresh badge
    } catch (error) {
      console.error('Failed to mark message as read:', error);
      throw error;
    }
  }

  // Mark all messages in conversation as read
  async markConversationAsRead(conversationId: string): Promise<void> {
    try {
      await api.put(`/messages/conversations/${conversationId}/read`);
      window.dispatchEvent(new Event('messagesUpdated')); // Notify app to refresh badge
    } catch (error) {
      console.error('Failed to mark conversation as read:', error);
      throw error;
    }
  }

  // Get unread message count
  async getUnreadCount(): Promise<number> {
    try {
      const response = await api.get(`/messages/unread-count`);
      return response.data.count;
    } catch (error) {
      console.error('Failed to fetch unread count:', error);
      return 0;
    }
  }

  // Start conversation with venue owner
  async startConversationWithOwner(ownerId: string, venueId?: string, venueType?: string): Promise<Conversation> {
    try {
      const response = await api.post(`/messages/conversations/start`, {
        participant_id: ownerId,
        venue_id: venueId,
        venue_type: venueType,
      });
      window.dispatchEvent(new Event('messagesUpdated')); // Notify app
      return transformConversation(response.data);
    } catch (error) {
      console.error('Failed to start conversation:', error);
      throw error;
    }
  }
}

export const messagingService = new MessagingService();
