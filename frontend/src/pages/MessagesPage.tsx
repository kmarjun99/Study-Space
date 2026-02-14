import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Card, Button, Input } from '../components/UI';
import { MessageCircle, Send, ArrowLeft, User as UserIcon, Search, RefreshCw, Check, CheckCheck } from 'lucide-react';
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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
  // Handle query parameters to start a conversation
  useEffect(() => {
    // Wait for initial load to complete so we don't start duplicate conversations
    if (isLoading) return;

    const ownerId = searchParams.get('owner');
    const venueId = searchParams.get('venue');
    const venueType = searchParams.get('type');

    // Only proceed if we have an ownerId and no conversation is currently selected
    // AND we haven't already just created/selected one (to prevent loop)
    if (ownerId && !selectedConversation) {
      const existing = conversations.find(conv =>
        conv.participants.some(p => p.id === ownerId) &&
        (!venueId || conv.venueId === venueId) // Optional: Match venue if provided
      );

      if (existing) {
        setSelectedConversation(existing);
      } else {
        startNewConversation(ownerId, venueId || undefined, venueType || undefined);
      }
    }
  }, [searchParams, conversations, selectedConversation, isLoading]);

  // Fetch messages when conversation is selected
  useEffect(() => {
    if (selectedConversation) {
      fetchMessages(selectedConversation.id);
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

  const startNewConversation = async (ownerId: string, venueId?: string, venueType?: string) => {
    try {
      const newConv = await messagingService.startConversationWithOwner(ownerId, venueId, venueType);
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

    const messageContent = newMessage.trim();
    setNewMessage('');
    setIsSending(true);

    // Optimistically add message to UI
    const optimisticMessage: Message = {
      id: 'temp-' + Date.now(),
      conversationId: selectedConversation.id,
      senderId: currentUserId,
      senderName: 'You',
      senderRole: currentUserRole,
      receiverId: otherParticipant.id,
      receiverName: otherParticipant.name,
      receiverRole: otherParticipant.role,
      content: messageContent,
      timestamp: new Date().toISOString(),
      read: false
    };

    setMessages([...messages, optimisticMessage]);

    try {
      const sentMessage = await messagingService.sendMessage(
        otherParticipant.id,
        messageContent,
        selectedConversation.venueId
      );

      // Replace optimistic message with real one
      setMessages(msgs => msgs.map(m => m.id === optimisticMessage.id ? sentMessage : m));

      // Update conversation last message
      setConversations(conversations.map(conv =>
        conv.id === selectedConversation.id
          ? { ...conv, lastMessage: sentMessage }
          : conv
      ));

    } catch (error: any) {
      console.error('Failed to send message:', error);
      toast.error(error.response?.data?.detail || 'Failed to send message');
      // Remove optimistic message on failure
      setMessages(msgs => msgs.filter(m => m.id !== optimisticMessage.id));
      setNewMessage(messageContent); // Restore message
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

  // Helper to get display name based on user role
  const getDisplayName = (conversation: Conversation, otherParticipant: any) => {
    if (currentUserRole === UserRole.STUDENT && conversation.venueName) {
      return conversation.venueName;
    }
    return otherParticipant?.name || 'Unknown User';
  };

  // Helper to get subtitle/context based on user role
  const getDisplayContext = (conversation: Conversation, otherParticipant: any) => {
    if (currentUserRole === UserRole.STUDENT) {
      // If student sees Venue Name as main title, show specific owner name or location as subtitle?
      // Or just keep it simple. Let's show "Venue Owner" or address if available?
      // For now, let's keep the existing logic but maybe tweak it.
      return otherParticipant?.role === UserRole.ADMIN ? 'Venue Owner' : 'Student';
    }
    // For Owners, they see Student Name. Context is fine.
    return 'Student';
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

  const formatMessageTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
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
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 sm:px-6 py-4 bg-white border-b border-gray-200 flex-shrink-0">
        <div className="flex items-center gap-3">
          <MessageCircle className="w-7 h-7 text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Messages</h1>
          {conversations.length > 0 && conversations.reduce((sum, conv) => sum + (conv.unreadCount || 0), 0) > 0 && (
            <span className="bg-red-500 text-white px-2.5 py-0.5 rounded-full text-xs font-bold">
              {conversations.reduce((sum, conv) => sum + (conv.unreadCount || 0), 0)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-3 py-2"
            size="sm"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-0 overflow-hidden min-h-0">
        {/* Conversations Sidebar */}
        <div className={`lg:col-span-4 border-r border-gray-200 flex flex-col bg-white overflow-hidden ${selectedConversation ? 'hidden lg:flex' : 'flex'}`}>
          {/* Search Bar */}
          <div className="p-3 border-b border-gray-200 bg-gray-50 flex-none">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 text-sm border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Conversations List */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {filteredConversations.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-500 p-6">
                <MessageCircle className="w-16 h-16 mb-3 text-gray-300" />
                <p className="font-medium text-center">{searchQuery ? 'No matching conversations' : 'No conversations yet'}</p>
                <p className="text-sm mt-2 text-center text-gray-400">
                  {searchQuery
                    ? 'Try a different search term'
                    : currentUserRole === UserRole.STUDENT
                      ? 'Contact venue owners to start chatting'
                      : 'Students will message you about your venues'}
                </p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {filteredConversations.map(conversation => {
                  const otherParticipant = getOtherParticipant(conversation);
                  if (!otherParticipant) return null;
                  const isSelected = selectedConversation?.id === conversation.id;

                  return (
                    <div
                      key={conversation.id}
                      onClick={() => setSelectedConversation(conversation)}
                      className={`p-4 cursor-pointer transition-all hover:bg-gray-50 ${isSelected ? 'bg-indigo-50 border-l-4 border-indigo-600' : ''
                        }`}
                    >
                      <div className="flex items-start gap-3">
                        {/* Avatar */}
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-400 to-indigo-600 flex items-center justify-center flex-shrink-0 text-white font-bold text-lg">
                          {otherParticipant?.avatarUrl ? (
                            <img src={otherParticipant.avatarUrl} alt={otherParticipant.name || 'User'} className="w-full h-full rounded-full object-cover" />
                          ) : (
                            (otherParticipant?.name || 'U').charAt(0).toUpperCase()
                          )}
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <h3 className="font-semibold text-gray-900 truncate text-sm">
                              {getDisplayName(conversation, otherParticipant)}
                            </h3>
                            {conversation.lastMessage && (
                              <span className="text-xs text-gray-500 ml-2 flex-shrink-0">
                                {formatTimestamp(conversation.lastMessage.timestamp)}
                              </span>
                            )}
                          </div>

                          <div className="flex items-center justify-between">
                            <p className="text-xs text-gray-500 mb-1">
                              {/* Venue Context with Type Badge */}
                              <span className="flex items-center gap-1.5 flex-wrap">
                                <span>{otherParticipant?.role === UserRole.ADMIN ? 'Owner' : 'Student'}</span>
                                {/* For Owner: Show Venue Name context */}
                                {conversation.venueName && currentUserRole !== UserRole.STUDENT && (
                                  <>
                                    <span>•</span>
                                    <span className="truncate max-w-[100px]">{conversation.venueName}</span>
                                  </>
                                )}
                                {/* For Student: Show Owner Name context (since Title is Venue Name) */}
                                {currentUserRole === UserRole.STUDENT && (
                                  <>
                                    <span>•</span>
                                    <span className="truncate max-w-[100px]">{otherParticipant?.name}</span>
                                  </>
                                )}
                                {conversation.venueType && (
                                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${conversation.venueType === 'reading_room'
                                      ? 'bg-blue-50 text-blue-600 border-blue-100' // Reading Room
                                      : 'bg-emerald-50 text-emerald-600 border-emerald-100' // Accommodation/Housing
                                    }`}>
                                    {conversation.venueType === 'reading_room' ? 'READING ROOM' : 'HOUSING'}
                                  </span>
                                )}
                              </span>
                            </p>
                          </div>

                          {conversation.lastMessage && (
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-sm text-gray-600 truncate flex-1">
                                {conversation.lastMessage.senderId === currentUserId && (
                                  <span className="text-indigo-600 mr-1">You:</span>
                                )}
                                {conversation.lastMessage.content}
                              </p>
                              {conversation.unreadCount > 0 && (
                                <span className="bg-indigo-600 text-white text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0 min-w-[20px] text-center">
                                  {conversation.unreadCount}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Chat Area */}
        <div className={`lg:col-span-8 flex flex-col bg-white overflow-hidden min-h-0 ${!selectedConversation ? 'hidden lg:flex' : 'flex'}`}>
          {!selectedConversation ? (
            <div className="flex items-center justify-center h-full text-gray-400 p-8 bg-gray-50">
              <div className="text-center">
                <MessageCircle className="w-20 h-20 mx-auto mb-4 text-gray-300" />
                <p className="text-lg font-medium text-gray-600">Select a conversation</p>
                <p className="text-sm text-gray-500 mt-2">Choose from your conversations to start messaging</p>
              </div>
            </div>
          ) : (
            <>
              {/* Chat Header */}
              <div className="px-4 py-3 border-b border-gray-200 bg-white flex items-center gap-3 shadow-sm flex-none">
                <button
                  onClick={() => setSelectedConversation(null)}
                  className="lg:hidden p-2 hover:bg-gray-100 rounded-full transition-colors"
                  aria-label="Back to conversations"
                >
                  <ArrowLeft className="w-5 h-5 text-gray-600" />
                </button>

                {/* Participant Info */}
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-400 to-indigo-600 flex items-center justify-center flex-shrink-0 text-white font-bold">
                  {getOtherParticipant(selectedConversation)?.avatarUrl ? (
                    <img
                      src={getOtherParticipant(selectedConversation)!.avatarUrl}
                      alt={getOtherParticipant(selectedConversation)?.name || 'User'}
                      className="w-full h-full rounded-full object-cover"
                    />
                  ) : (
                    (getOtherParticipant(selectedConversation)?.name || 'U').charAt(0).toUpperCase()
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 truncate">
                    {getDisplayName(selectedConversation, getOtherParticipant(selectedConversation))}
                  </h3>
                  <p className="text-xs text-gray-500 truncate">
                    {/* Keep the context info, maybe flip it if needed */}
                    {getOtherParticipant(selectedConversation)?.role === UserRole.ADMIN ? 'Venue Owner' : 'Student'}
                    {selectedConversation.venueName && currentUserRole !== UserRole.STUDENT && ` • ${selectedConversation.venueName}`}
                    {/* If student, they already see venue name as title, so maybe show owner name here? */}
                    {currentUserRole === UserRole.STUDENT && ` • ${getOtherParticipant(selectedConversation)?.name}`}
                  </p>
                </div>
              </div>

              {/* Messages Area - WhatsApp Style */}
              <div
                className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0"
                style={{
                  backgroundImage: 'linear-gradient(to bottom, #f0f0f0 0%, #e8e8e8 100%)'
                }}
              >
                {messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-gray-500">
                    <div className="bg-white rounded-lg shadow-sm px-6 py-4 text-center">
                      <MessageCircle className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                      <p className="font-medium text-gray-700">No messages yet</p>
                      <p className="text-sm mt-1 text-gray-500">Start the conversation by sending a message</p>
                    </div>
                  </div>
                ) : (
                  <>
                    {messages.map((message, index) => {
                      const isOwnMessage = message.senderId === currentUserId;
                      const showAvatar = !isOwnMessage && (index === 0 || messages[index - 1].senderId !== message.senderId);

                      return (
                        <div
                          key={message.id}
                          className={`flex items-end gap-2 ${isOwnMessage ? 'justify-end' : 'justify-start'}`}
                        >
                          {/* Avatar for received messages - LEFT SIDE */}
                          {!isOwnMessage && (
                            <div className={`w-8 h-8 rounded-full flex-shrink-0 self-end mb-1 ${showAvatar ? 'visible' : 'invisible'}`}>
                              <div className="w-8 h-8 rounded-full bg-gray-400 flex items-center justify-center text-white text-xs font-bold">
                                {(message.senderName || 'U').charAt(0).toUpperCase()}
                              </div>
                            </div>
                          )}

                          {/* Message Bubble */}
                          <div className={`max-w-[75%] sm:max-w-[60%]`}>
                            <div
                              className={`rounded-2xl px-4 py-2 shadow-sm ${isOwnMessage
                                ? 'bg-indigo-600 text-white rounded-br-md'
                                : 'bg-white text-gray-900 rounded-bl-md border border-gray-200'
                                }`}
                            >
                              {/* Sender name for received messages */}
                              {!isOwnMessage && showAvatar && message.senderName && (
                                <div className="text-xs font-semibold text-indigo-600 mb-1">
                                  {message.senderName}
                                </div>
                              )}

                              {/* Message Content */}
                              <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">
                                {message.content}
                              </p>

                              {/* Timestamp & Status */}
                              <div className={`flex items-center justify-end gap-1 mt-1 text-xs ${isOwnMessage ? 'text-indigo-200' : 'text-gray-500'
                                }`}>
                                <span>{formatMessageTime(message.timestamp)}</span>
                                {isOwnMessage && (
                                  message.read ? (
                                    <CheckCheck className="w-3.5 h-3.5" />
                                  ) : (
                                    <Check className="w-3.5 h-3.5" />
                                  )
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                    <div ref={messagesEndRef} />
                  </>
                )}
              </div>

              {/* Message Input - WhatsApp Style */}
              <div className="p-3 bg-gray-100 border-t border-gray-200">
                <div className="flex items-end gap-2">
                  <textarea
                    ref={textareaRef}
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Type a message..."
                    className="flex-1 px-4 py-3 bg-white border border-gray-300 rounded-3xl resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm max-h-32"
                    rows={1}
                    disabled={isSending}
                    style={{ minHeight: '44px' }}
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={!newMessage.trim() || isSending}
                    className={`p-3 rounded-full transition-all flex items-center justify-center ${newMessage.trim() && !isSending
                      ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg hover:shadow-xl'
                      : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      }`}
                    style={{ width: '44px', height: '44px' }}
                    aria-label="Send message"
                  >
                    {isSending ? (
                      <RefreshCw className="w-5 h-5 animate-spin" />
                    ) : (
                      <Send className="w-5 h-5" />
                    )}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-2 px-2">Press Enter to send, Shift+Enter for new line</p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
