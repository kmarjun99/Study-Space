import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Card, Button, Input } from '../components/UI';
import { MessageCircle, Send, ArrowLeft, User as UserIcon } from 'lucide-react';
import { messagingService } from '../services/messagingService';
import { Message, Conversation, UserRole } from '../types';

interface MessagesPageProps {
  currentUserId: string;
  currentUserRole: UserRole;
}

export const MessagesPage: React.FC<MessagesPageProps> = ({ currentUserId, currentUserRole }) => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch conversations on mount
  useEffect(() => {
    fetchConversations();
  }, []);

  // Handle query parameters to start a conversation
  useEffect(() => {
    const ownerId = searchParams.get('owner');
    const venueId = searchParams.get('venue');

    if (ownerId && conversations.length > 0 && !selectedConversation) {
      // Check if conversation already exists
      const existing = conversations.find(conv =>
        conv.participants.some(p => p.id === ownerId)
      );

      if (existing) {
        setSelectedConversation(existing);
      } else {
        // Start new conversation
        startNewConversation(ownerId, venueId || undefined);
      }
    }
  }, [searchParams, conversations, selectedConversation]);

  // Fetch messages when conversation is selected
  useEffect(() => {
    if (selectedConversation) {
      fetchMessages(selectedConversation.id);
      // Mark conversation as read
      messagingService.markConversationAsRead(selectedConversation.id).catch(console.error);
    }
  }, [selectedConversation]);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchConversations = async () => {
    try {
      setIsLoading(true);
      const data = await messagingService.getConversations();
      setConversations(data);
    } catch (error) {
      console.error('Failed to fetch conversations:', error);
      toast.error('Failed to load conversations');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchMessages = async (conversationId: string) => {
    try {
      const data = await messagingService.getMessages(conversationId);
      setMessages(data);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      toast.error('Failed to load messages');
    }
  };

  const startNewConversation = async (ownerId: string, venueId?: string) => {
    try {
      const newConv = await messagingService.startConversationWithOwner(ownerId, venueId);
      setConversations([newConv, ...conversations]);
      setSelectedConversation(newConv);
      toast.success('Conversation started');
    } catch (error) {
      console.error('Failed to start conversation:', error);
      toast.error('Failed to start conversation');
    }
  };

  const handleSendMessage = async () => {
    if (!selectedConversation || !newMessage.trim()) return;

    const otherParticipant = selectedConversation.participants.find(p => p.id !== currentUserId);
    if (!otherParticipant) return;

    setIsSending(true);
    try {
      const sentMessage = await messagingService.sendMessage(
        otherParticipant.id,
        newMessage.trim(),
        selectedConversation.venueId
      );
      
      setMessages([...messages, sentMessage]);
      setNewMessage('');
      
      // Update conversation last message
      setConversations(conversations.map(conv =>
        conv.id === selectedConversation.id
          ? { ...conv, lastMessage: sentMessage }
          : conv
      ));
      
      toast.success('Message sent');
    } catch (error) {
      console.error('Failed to send message:', error);
      toast.error('Failed to send message');
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const getOtherParticipant = (conversation: Conversation) => {
    return conversation.participants.find(p => p.id !== currentUserId);
  };

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 h-screen flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <MessageCircle className="w-8 h-8 text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Messages</h1>
        </div>
        {selectedConversation && (
          <Button variant="outline" onClick={() => setSelectedConversation(null)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Conversations
          </Button>
        )}
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
        {/* Conversations List */}
        <Card className={`p-4 overflow-y-auto ${selectedConversation && 'hidden lg:block'}`}>
          <h2 className="font-semibold text-lg mb-4">Conversations</h2>
          
          {conversations.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <MessageCircle className="w-16 h-16 mx-auto mb-4 text-gray-300" />
              <p>No conversations yet</p>
              <p className="text-sm mt-2">Messages from students and owners will appear here</p>
            </div>
          ) : (
            <div className="space-y-2">
              {conversations.map(conversation => {
                const otherParticipant = getOtherParticipant(conversation);
                if (!otherParticipant) return null;

                return (
                  <div
                    key={conversation.id}
                    onClick={() => setSelectedConversation(conversation)}
                    className={`p-4 rounded-lg border cursor-pointer transition-all hover:shadow-md ${
                      selectedConversation?.id === conversation.id
                        ? 'bg-indigo-50 border-indigo-300'
                        : 'bg-white border-gray-200 hover:border-indigo-200'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                        {otherParticipant.avatarUrl ? (
                          <img src={otherParticipant.avatarUrl} alt={otherParticipant.name} className="w-full h-full rounded-full object-cover" />
                        ) : (
                          <UserIcon className="w-5 h-5 text-indigo-600" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <h3 className="font-semibold text-gray-900 truncate">{otherParticipant.name}</h3>
                          {conversation.unreadCount > 0 && (
                            <span className="bg-indigo-600 text-white text-xs font-bold px-2 py-1 rounded-full">
                              {conversation.unreadCount}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mb-1">
                          {otherParticipant.role === UserRole.ADMIN ? 'Venue Owner' : 'Student'}
                          {conversation.venueName && ` • ${conversation.venueName}`}
                        </p>
                        {conversation.lastMessage && (
                          <p className="text-sm text-gray-600 truncate">
                            {conversation.lastMessage.senderId === currentUserId && 'You: '}
                            {conversation.lastMessage.content}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Messages Panel */}
        <Card className={`p-0 lg:col-span-2 flex flex-col ${!selectedConversation && 'hidden lg:flex'}`}>
          {!selectedConversation ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              <div className="text-center">
                <MessageCircle className="w-20 h-20 mx-auto mb-4 text-gray-300" />
                <p className="text-lg">Select a conversation to start messaging</p>
              </div>
            </div>
          ) : (
            <>
              {/* Chat Header */}
              <div className="p-4 border-b bg-gray-50 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
                  {getOtherParticipant(selectedConversation)?.avatarUrl ? (
                    <img 
                      src={getOtherParticipant(selectedConversation)!.avatarUrl} 
                      alt={getOtherParticipant(selectedConversation)!.name} 
                      className="w-full h-full rounded-full object-cover" 
                    />
                  ) : (
                    <UserIcon className="w-5 h-5 text-indigo-600" />
                  )}
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">
                    {getOtherParticipant(selectedConversation)?.name}
                  </h3>
                  <p className="text-xs text-gray-500">
                    {getOtherParticipant(selectedConversation)?.role === UserRole.ADMIN ? 'Venue Owner' : 'Student'}
                    {selectedConversation.venueName && ` • ${selectedConversation.venueName}`}
                  </p>
                </div>
              </div>

              {/* Messages Area */}
              <div className="flex-1 p-4 overflow-y-auto bg-gray-50" style={{ maxHeight: 'calc(100vh - 300px)' }}>
                {messages.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">
                    <p>No messages yet. Start the conversation!</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {messages.map((message, index) => {
                      const isOwnMessage = message.senderId === currentUserId;
                      const showSender = index === 0 || messages[index - 1].senderId !== message.senderId;

                      return (
                        <div key={message.id} className={`flex ${isOwnMessage ? 'justify-end' : 'justify-start'}`}>
                          <div className={`max-w-[70%] ${isOwnMessage ? 'items-end' : 'items-start'} flex flex-col`}>
                            {showSender && !isOwnMessage && (
                              <span className="text-xs text-gray-500 mb-1 ml-2">{message.senderName}</span>
                            )}
                            <div
                              className={`px-4 py-2 rounded-2xl ${
                                isOwnMessage
                                  ? 'bg-indigo-600 text-white rounded-br-sm'
                                  : 'bg-white text-gray-900 border border-gray-200 rounded-bl-sm'
                              }`}
                            >
                              <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
                            </div>
                            <span className="text-xs text-gray-400 mt-1 mx-2">
                              {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              {/* Message Input */}
              <div className="p-4 border-t bg-white">
                <div className="flex gap-2">
                  <textarea
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Type your message..."
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    rows={2}
                    disabled={isSending}
                  />
                  <Button
                    onClick={handleSendMessage}
                    disabled={!newMessage.trim() || isSending}
                    className="self-end"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
};
