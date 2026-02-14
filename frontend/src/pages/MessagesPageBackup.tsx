import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Card, Button, Input } from '../components/UI';
import { MessageCircle, Send, ArrowLeft, User as UserIcon, Search, RefreshCw, Clock } from 'lucide-react';
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
  const [searchQuery, setSearchQuery] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch conversations on mount and setup polling
  useEffect(() => {
    fetchConversations();
    
    // Poll for new messages every 10 seconds
    pollIntervalRef.current = setInterval(() => {
      fetchConversations(true); // Silent refresh
      if (selectedConversation) {
        fetchMessages(selectedConversation.id, true);
      }
    }, 10000);
    
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [selectedConversation]);

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

  const fetchConversations = async (silent = false) => {
    try {
      if (!silent) setIsLoading(true);
      const data = await messagingService.getConversations();
      setConversations(data);
    } catch (error: any) {
      console.error('Failed to fetch conversations:', error);
      if (!silent) {
        const message = error.response?.data?.detail || 'Failed to load conversations';
        toast.error(message);
      }
    } finally {
      if (!silent) setIsLoading(false);
    }
  };

  const fetchMessages = async (conversationId: string, silent = false) => {
    try {
      const data = await messagingService.getMessages(conversationId);
      setMessages(data);
    } catch (error: any) {
      console.error('Failed to fetch messages:', error);
      if (!silent) {
        toast.error(error.response?.data?.detail || 'Failed to load messages');
      }
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchConversations();
    if (selectedConversation) {
      await fetchMessages(selectedConversation.id);
    }
    setIsRefreshing(false);
    toast.success('Refreshed');
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

  const filteredConversations = conversations.filter(conv => {
    if (!searchQuery.trim()) return true;
    const otherParticipant = getOtherParticipant(conv);
    return otherParticipant?.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
           conv.lastMessage?.content.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
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
      <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <MessageCircle className="w-8 h-8 text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Messages</h1>
          {conversations.length > 0 && (
            <span className="bg-indigo-100 text-indigo-600 px-3 py-1 rounded-full text-sm font-medium">
              {conversations.reduce((sum, conv) => sum + (conv.unreadCount || 0), 0)} unread
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          {selectedConversation && (
            <Button variant="outline" onClick={() => setSelectedConversation(null)} className="lg:hidden">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
        {/* Conversations List */}
        <Card className={`p-4 overflow-y-auto ${selectedConversation && 'hidden lg:block'}`}>
          <div className="mb-4">
            <h2 className="font-semibold text-lg mb-3">Conversations</h2>
            {conversations.length > 0 && (
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search conversations..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            )}
          </div>
          
          {filteredConversations.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <MessageCircle className="w-16 h-16 mx-auto mb-4 text-gray-300" />
              <p className="font-medium">{searchQuery ? 'No matching conversations' : 'No conversations yet'}</p>
              <p className="text-sm mt-2">
                {searchQuery 
                  ? 'Try a different search term'
                  : currentUserRole === UserRole.STUDENT 
                    ? 'Contact venue owners to start a conversation'
                    : 'Students will message you about your venues'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredConversations.map(conversation => {
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
                            <span className="bg-indigo-600 text-white text-xs font-bold px-2 py-1 rounded-full ml-2">
                              {conversation.unreadCount}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mb-1">
                          {otherParticipant.role === UserRole.ADMIN ? 'Venue Owner' : 'Student'}
                          {conversation.venueName && ` • ${conversation.venueName}`}
                        </p>
                        {conversation.lastMessage && (
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-sm text-gray-600 truncate flex-1">
                              {conversation.lastMessage.senderId === currentUserId && 'You: '}
                              {conversation.lastMessage.content}
                            </p>
                            <span className="text-xs text-gray-400 whitespace-nowrap flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {formatTimestamp(conversation.lastMessage.timestamp)}
                            </span>
                          </div>
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
            <div className="flex items-center justify-center h-full text-gray-400 p-8">
              <div className="text-center">
                <MessageCircle className="w-20 h-20 mx-auto mb-4 text-gray-300" />
                <p className="text-lg font-medium text-gray-600">Select a conversation to start messaging</p>
                <p className="text-sm text-gray-500 mt-2">Choose from your conversations on the left</p>
              </div>
            </div>
          ) : (
            <>
              {/* Chat Header */}
              <div className="p-4 border-b bg-gray-50 flex items-center gap-3">
                <button
                  onClick={() => setSelectedConversation(null)}
                  className="lg:hidden p-2 hover:bg-gray-200 rounded-full transition-colors"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>
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
                <div className="flex-1">
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
                    <MessageCircle className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                    <p className="font-medium">No messages yet</p>
                    <p className="text-sm mt-1">Start the conversation by sending a message below</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {messages.map((message, index) => {
                      const isOwnMessage = message.senderId === currentUserId;
                      const showSender = index === 0 || messages[index - 1].senderId !== message.senderId;
                      const showTimestamp = index === messages.length - 1 || 
                                           messages[index + 1].senderId !== message.senderId ||
                                           new Date(messages[index + 1].timestamp).getTime() - new Date(message.timestamp).getTime() > 300000;

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
                                  : 'bg-white text-gray-900 border border-gray-200 rounded-bl-sm shadow-sm'
                              }`}
                            >
                              <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
                            </div>
                            {showTimestamp && (
                              <span className="text-xs text-gray-400 mt-1 mx-2">
                                {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </span>
                            )}
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
                    placeholder="Type your message... (Press Enter to send)"
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    rows={2}
                    disabled={isSending}
                  />
                  <Button
                    onClick={handleSendMessage}
                    disabled={!newMessage.trim() || isSending}
                    className="self-end"
                  >
                    {isSending ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
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
