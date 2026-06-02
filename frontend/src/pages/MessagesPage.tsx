import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Button } from '../components/UI';
import {
  MessageCircle, Send, ArrowLeft, Search, RefreshCw, Check, CheckCheck,
} from 'lucide-react';
import {
  messagingService,
  messagingWebSocket,
  MessageEvent as WsMessageEvent,
} from '../services/messagingService';
import { Message, Conversation, UserRole } from '../types';

interface MessagesPageProps {
  currentUserId: string;
  currentUserRole: UserRole;
}

const QUICK_REPLIES_HIDDEN_KEY = 'messages.quickReplies.hidden';
const MAX_MESSAGE_LENGTH = 1000;

export const MessagesPage: React.FC<MessagesPageProps> = ({ currentUserId, currentUserRole }) => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Data
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  // Composer / UI
  const [newMessage, setNewMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [messageSearchQuery, setMessageSearchQuery] = useState('');
  const [showMessageSearch, setShowMessageSearch] = useState(false);
  const [showQuickReplies, setShowQuickReplies] = useState(
    () => localStorage.getItem(QUICK_REPLIES_HIDDEN_KEY) !== '1',
  );
  const [isOtherTyping, setIsOtherTyping] = useState(false);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Latest selectedConversation snapshot for use inside stable callbacks (WS / typing)
  const selectedConvRef = useRef<Conversation | null>(null);
  selectedConvRef.current = selectedConversation;
  const typingTimeoutRef = useRef<number | null>(null);
  const typingDebounceRef = useRef<number | null>(null);

  // ============================================================
  // Quick reply templates
  // ============================================================
  const quickReplies = useMemo(
    () => (currentUserRole === UserRole.STUDENT
      ? [
          'Is this cabin available?',
          'What are the timings?',
          'Can I book for tomorrow?',
          'Thanks for the info!',
        ]
      : [
          "Yes, it's available!",
          'Let me check and get back to you.',
          'Feel free to visit anytime.',
          "You're welcome!",
        ]),
    [currentUserRole],
  );

  // ============================================================
  // Initial load
  // ============================================================
  const fetchConversations = useCallback(async (silent = false) => {
    try {
      if (!silent) setIsLoading(true);
      const data = await messagingService.getConversations();
      setConversations(data);
    } catch (error: any) {
      console.error('Failed to fetch conversations:', error);
      if (!silent) {
        toast.error(error.response?.data?.detail || 'Failed to load conversations');
      }
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  const fetchMessages = useCallback(async (conversationId: string, silent = false) => {
    try {
      const data = await messagingService.getMessages(conversationId);
      setMessages(data);
    } catch (error: any) {
      console.error('Failed to fetch messages:', error);
      if (!silent) {
        toast.error(error.response?.data?.detail || 'Failed to load messages');
      }
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // ============================================================
  // WebSocket — real-time updates
  // ============================================================
  useEffect(() => {
    if (!currentUserId) return;

    messagingWebSocket.connect(currentUserId);

    const unsubscribe = messagingWebSocket.subscribe((event: WsMessageEvent) => {
      const currentConv = selectedConvRef.current;

      if (event.type === 'NEW_MESSAGE') {
        const incoming = event.payload;

        // Append to currently open chat (skip our own echo if already optimistic)
        if (currentConv && incoming.conversationId === currentConv.id) {
          setMessages((prev) => {
            if (prev.some((m) => m.id === incoming.id)) return prev;
            return [...prev, incoming];
          });
          // Auto-mark as read since the chat is open and the message is for us
          if (incoming.receiverId === currentUserId) {
            messagingService.markConversationAsRead(currentConv.id).catch(() => {});
          }
        }

        // Update conversation list (move to top, update preview, bump unread)
        setConversations((prev) => {
          const existing = prev.find((c) => c.id === incoming.conversationId);
          if (!existing) {
            // New conversation arrived; refetch list to get full participant data
            fetchConversations(true);
            return prev;
          }
          const isOpen = currentConv?.id === incoming.conversationId;
          const updated: Conversation = {
            ...existing,
            lastMessage: incoming,
            unreadCount:
              incoming.receiverId === currentUserId && !isOpen
                ? (existing.unreadCount || 0) + 1
                : existing.unreadCount || 0,
          };
          const others = prev.filter((c) => c.id !== incoming.conversationId);
          return [updated, ...others];
        });
      }

      if (event.type === 'MESSAGE_READ') {
        if (currentConv && event.payload.conversationId === currentConv.id) {
          setMessages((prev) => prev.map((m) => (m.id === event.payload.messageId ? { ...m, read: true } : m)));
        }
      }

      if (event.type === 'CONVERSATION_READ') {
        if (currentConv && event.payload.conversationId === currentConv.id) {
          setMessages((prev) => prev.map((m) => (
            m.senderId === currentUserId ? { ...m, read: true } : m
          )));
        }
      }

      if (event.type === 'TYPING') {
        if (
          currentConv
          && event.payload.conversationId === currentConv.id
          && event.payload.userId !== currentUserId
        ) {
          setIsOtherTyping(event.payload.isTyping);
          if (event.payload.isTyping) {
            if (typingTimeoutRef.current) window.clearTimeout(typingTimeoutRef.current);
            typingTimeoutRef.current = window.setTimeout(() => setIsOtherTyping(false), 4000);
          }
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, [currentUserId, fetchConversations]);

  // ============================================================
  // Handle deep links: /messages?owner=...&venue=...&type=...
  // ============================================================
  useEffect(() => {
    if (isLoading) return;

    const ownerId = searchParams.get('owner');
    const venueId = searchParams.get('venue');
    const venueType = searchParams.get('type');

    if (ownerId && !selectedConversation) {
      const existing = conversations.find((conv) =>
        conv.participants.some((p) => p.id === ownerId)
        && (!venueId || conv.venueId === venueId),
      );

      if (existing) {
        setSelectedConversation(existing);
      } else {
        startNewConversation(ownerId, venueId || undefined, venueType || undefined);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, conversations, selectedConversation, isLoading]);

  // ============================================================
  // Fetch messages when conversation changes; mark as read
  // ============================================================
  useEffect(() => {
    if (selectedConversation) {
      setIsOtherTyping(false);
      fetchMessages(selectedConversation.id);
      messagingService.markConversationAsRead(selectedConversation.id)
        .then(() => {
          setConversations((prev) => prev.map((c) =>
            c.id === selectedConversation.id ? { ...c, unreadCount: 0 } : c,
          ));
        })
        .catch(() => {});
    }
  }, [selectedConversation, fetchMessages]);

  // ============================================================
  // Auto-scroll on new messages
  // ============================================================
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isOtherTyping]);

  // ============================================================
  // Derived data
  // ============================================================
  const filteredMessages = useMemo(() => {
    if (!messageSearchQuery) return messages;
    const q = messageSearchQuery.toLowerCase();
    return messages.filter((msg) => msg.content.toLowerCase().includes(q));
  }, [messages, messageSearchQuery]);

  const totalUnread = useMemo(
    () => conversations.reduce((sum, conv) => sum + (conv.unreadCount || 0), 0),
    [conversations],
  );

  const filteredConversations = useMemo(() => conversations.filter((conv) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const otherParticipant = conv.participants.find((p) => p.id !== currentUserId);
    return (
      otherParticipant?.name.toLowerCase().includes(q)
      || conv.venueName?.toLowerCase().includes(q)
      || conv.lastMessage?.content.toLowerCase().includes(q)
    );
  }), [conversations, searchQuery, currentUserId]);

  // ============================================================
  // Actions
  // ============================================================
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
      setConversations((prev) => {
        if (prev.some((c) => c.id === newConv.id)) return prev;
        return [newConv, ...prev];
      });
      setSelectedConversation(newConv);
      toast.success('Conversation started');
    } catch (error) {
      console.error('Failed to start conversation:', error);
      toast.error('Failed to start conversation');
    }
  };

  const handleSendMessage = async () => {
    if (!selectedConversation || !newMessage.trim() || isSending) return;
    if (newMessage.length > MAX_MESSAGE_LENGTH) {
      toast.error(`Message too long (max ${MAX_MESSAGE_LENGTH} characters)`);
      return;
    }

    const otherParticipant = selectedConversation.participants.find((p) => p.id !== currentUserId);
    if (!otherParticipant) return;

    const messageContent = newMessage.trim();
    setNewMessage('');
    setIsSending(true);

    const optimisticId = 'temp-' + Date.now();
    const optimisticMessage: Message = {
      id: optimisticId,
      conversationId: selectedConversation.id,
      senderId: currentUserId,
      senderName: 'You',
      senderRole: currentUserRole,
      receiverId: otherParticipant.id,
      receiverName: otherParticipant.name,
      receiverRole: otherParticipant.role,
      content: messageContent,
      timestamp: new Date().toISOString(),
      read: false,
    };
    setMessages((prev) => [...prev, optimisticMessage]);

    try {
      const sentMessage = await messagingService.sendMessage(
        otherParticipant.id,
        messageContent,
        selectedConversation.venueId,
        selectedConversation.venueType,
      );
      // Replace optimistic message with the server-assigned one
      setMessages((msgs) => {
        // Avoid duplicates if WebSocket already delivered it
        const withoutOptimistic = msgs.filter((m) => m.id !== optimisticId);
        if (withoutOptimistic.some((m) => m.id === sentMessage.id)) return withoutOptimistic;
        return [...withoutOptimistic, sentMessage];
      });
      setConversations((prev) => prev.map((conv) =>
        conv.id === selectedConversation.id ? { ...conv, lastMessage: sentMessage } : conv,
      ));
    } catch (error: any) {
      console.error('Failed to send message:', error);
      toast.error(error.response?.data?.detail || 'Failed to send message');
      setMessages((msgs) => msgs.filter((m) => m.id !== optimisticId));
      setNewMessage(messageContent);
    } finally {
      setIsSending(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    if (value.length > MAX_MESSAGE_LENGTH) {
      setNewMessage(value.slice(0, MAX_MESSAGE_LENGTH));
      return;
    }
    setNewMessage(value);

    // Debounced typing indicator
    const conv = selectedConvRef.current;
    if (!conv) return;
    const otherParticipant = conv.participants.find((p) => p.id !== currentUserId);
    if (!otherParticipant) return;

    if (typingDebounceRef.current) window.clearTimeout(typingDebounceRef.current);
    if (value.trim().length > 0) {
      messagingService.sendTyping(otherParticipant.id, conv.id, true);
      typingDebounceRef.current = window.setTimeout(() => {
        messagingService.sendTyping(otherParticipant.id, conv.id, false);
      }, 2500);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleQuickReplyClick = (reply: string) => {
    setNewMessage(reply);
    textareaRef.current?.focus();
  };

  const handleHideQuickReplies = () => {
    setShowQuickReplies(false);
    localStorage.setItem(QUICK_REPLIES_HIDDEN_KEY, '1');
  };

  const handleShowQuickReplies = () => {
    setShowQuickReplies(true);
    localStorage.removeItem(QUICK_REPLIES_HIDDEN_KEY);
  };

  // ============================================================
  // Helpers
  // ============================================================
  const getOtherParticipant = (conversation: Conversation) =>
    conversation.participants.find((p) => p.id !== currentUserId);

  const getDisplayName = (conversation: Conversation, otherParticipant: any) => {
    if (currentUserRole === UserRole.STUDENT && conversation.venueName) {
      return conversation.venueName;
    }
    return otherParticipant?.name || 'Unknown User';
  };

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

  const formatMessageTime = (timestamp: string) =>
    new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  // ============================================================
  // Render
  // ============================================================
  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600" />
        </div>
      </div>
    );
  }

  // Mobile layout contract with Layout.tsx:
  //   - top app header is h-14 (56px) sticky at top
  //   - bottom nav is h-16 (64px) + env(safe-area-inset-bottom) fixed at bottom
  //   - main is overflow-y-auto with pb-32 — using `h-screen` here would make
  //     the whole page scroll instead of just the message list.
  // So on mobile we use position: fixed to escape main's scroll/padding and
  // pin the chat between the top header and the bottom nav. Only the inner
  // messages list scrolls. On desktop (md+) we revert to the original
  // h-screen flex layout (no mobile header, no bottom nav).
  return (
    <div
      className="
        flex flex-col bg-white overflow-hidden
        fixed inset-x-0 top-14 z-20
        bottom-[calc(4rem+env(safe-area-inset-bottom,0px))]
        md:static md:inset-auto md:top-auto md:bottom-auto md:z-auto
        md:h-screen
      "
    >
      {/* Page-level header. On MOBILE this is shown only when no
          conversation is open (i.e., the user is on the conversation
          list). Once a chat is opened on mobile, this is hidden so the
          chat gets maximum vertical real estate — only the compact chat
          header (back button + avatar + name) remains, matching the
          WhatsApp / Instagram DM convention.
          Desktop (lg+) always shows this header since the split-view
          layout keeps the conversation list visible alongside the chat. */}
      <div
        className={`items-center justify-between px-4 sm:px-6 py-4 bg-white border-b border-gray-200 flex-shrink-0 ${
          selectedConversation ? 'hidden lg:flex' : 'flex'
        }`}
      >
        <div className="flex items-center gap-3">
          <MessageCircle className="w-7 h-7 text-indigo-600" />
          <h1 className="text-2xl font-bold text-gray-900">Messages</h1>
          {totalUnread > 0 && (
            <span className="bg-red-500 text-white px-2.5 py-0.5 rounded-full text-xs font-bold">
              {totalUnread}
            </span>
          )}
        </div>
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

      {/* Main */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-0 overflow-hidden min-h-0">
        {/* Sidebar */}
        <div className={`lg:col-span-4 border-r border-gray-200 flex flex-col bg-white overflow-hidden ${selectedConversation ? 'hidden lg:flex' : 'flex'}`}>
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
                {filteredConversations.map((conversation) => {
                  const otherParticipant = getOtherParticipant(conversation);
                  if (!otherParticipant) return null;
                  const isSelected = selectedConversation?.id === conversation.id;

                  return (
                    <div
                      key={conversation.id}
                      onClick={() => setSelectedConversation(conversation)}
                      className={`p-4 cursor-pointer transition-all hover:bg-gray-50 ${isSelected ? 'bg-indigo-50 border-l-4 border-indigo-600' : ''}`}
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-400 to-indigo-600 flex items-center justify-center flex-shrink-0 text-white font-bold text-lg">
                          {otherParticipant?.avatarUrl ? (
                            <img src={otherParticipant.avatarUrl} alt={otherParticipant.name || 'User'} className="w-full h-full rounded-full object-cover" />
                          ) : (
                            (otherParticipant?.name || 'U').charAt(0).toUpperCase()
                          )}
                        </div>
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
                              <span className="flex items-center gap-1.5 flex-wrap">
                                <span>{otherParticipant?.role === UserRole.ADMIN ? 'Owner' : 'Student'}</span>
                                {conversation.venueName && currentUserRole !== UserRole.STUDENT && (
                                  <>
                                    <span>•</span>
                                    <span className="truncate max-w-[100px]">{conversation.venueName}</span>
                                  </>
                                )}
                                {currentUserRole === UserRole.STUDENT && (
                                  <>
                                    <span>•</span>
                                    <span className="truncate max-w-[100px]">{otherParticipant?.name}</span>
                                  </>
                                )}
                                {conversation.venueType && (
                                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${conversation.venueType === 'reading_room'
                                    ? 'bg-blue-50 text-blue-600 border-blue-100'
                                    : 'bg-emerald-50 text-emerald-600 border-emerald-100'}`}>
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
              <div className="px-4 py-3 border-b border-gray-200 bg-white flex items-center justify-between gap-3 shadow-sm flex-none">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <button
                    onClick={() => setSelectedConversation(null)}
                    className="lg:hidden p-2 hover:bg-gray-100 rounded-full transition-colors"
                    aria-label="Back to conversations"
                  >
                    <ArrowLeft className="w-5 h-5 text-gray-600" />
                  </button>
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
                    <p className="text-xs text-gray-500 truncate flex items-center gap-1">
                      {isOtherTyping ? (
                        <span className="text-indigo-600 font-medium">typing…</span>
                      ) : (
                        <>
                          {getOtherParticipant(selectedConversation)?.role === UserRole.ADMIN ? 'Venue Owner' : 'Student'}
                          {selectedConversation.venueName && currentUserRole !== UserRole.STUDENT && ` • ${selectedConversation.venueName}`}
                          {currentUserRole === UserRole.STUDENT && ` • ${getOtherParticipant(selectedConversation)?.name}`}
                        </>
                      )}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowMessageSearch(!showMessageSearch)}
                  className={`p-2 rounded-full transition-colors ${showMessageSearch ? 'bg-indigo-100 text-indigo-600' : 'hover:bg-gray-100 text-gray-600'}`}
                  aria-label="Search messages"
                >
                  <Search className="w-5 h-5" />
                </button>
              </div>

              {showMessageSearch && (
                <div className="p-3 bg-gray-50 border-b border-gray-200 flex-none">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="text"
                      placeholder="Search in conversation..."
                      value={messageSearchQuery}
                      onChange={(e) => setMessageSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      autoFocus
                    />
                    {messageSearchQuery && (
                      <button
                        onClick={() => setMessageSearchQuery('')}
                        className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        ×
                      </button>
                    )}
                  </div>
                  {messageSearchQuery && (
                    <p className="text-xs text-gray-500 mt-2">
                      Found {filteredMessages.length} message{filteredMessages.length !== 1 ? 's' : ''}
                    </p>
                  )}
                </div>
              )}

              {/* Messages */}
              <div
                className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0"
                style={{ backgroundImage: 'linear-gradient(to bottom, #f0f0f0 0%, #e8e8e8 100%)' }}
              >
                {filteredMessages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-gray-500">
                    <div className="bg-white rounded-lg shadow-sm px-6 py-4 text-center">
                      <MessageCircle className="w-12 h-12 mx-auto mb-3 text-gray-400" />
                      <p className="font-medium text-gray-700">
                        {messageSearchQuery ? 'No messages found' : 'No messages yet'}
                      </p>
                      <p className="text-sm mt-1 text-gray-500">
                        {messageSearchQuery ? 'Try a different search term' : 'Start the conversation by sending a message'}
                      </p>
                    </div>
                  </div>
                ) : (
                  <>
                    {filteredMessages.map((message, index) => {
                      const prevMessage = index > 0 ? filteredMessages[index - 1] : null;
                      const isOwnMessage = message.senderId === currentUserId;
                      const showAvatar = !isOwnMessage && (index === 0 || prevMessage?.senderId !== message.senderId);
                      const isHighlighted = !!messageSearchQuery
                        && message.content.toLowerCase().includes(messageSearchQuery.toLowerCase());

                      return (
                        <div
                          key={message.id}
                          className={`flex items-end gap-2 ${isOwnMessage ? 'justify-end' : 'justify-start'}`}
                        >
                          {!isOwnMessage && (
                            <div className={`w-8 h-8 rounded-full flex-shrink-0 self-end mb-1 ${showAvatar ? 'visible' : 'invisible'}`}>
                              <div className="w-8 h-8 rounded-full bg-gray-400 flex items-center justify-center text-white text-xs font-bold">
                                {(message.senderName || 'U').charAt(0).toUpperCase()}
                              </div>
                            </div>
                          )}
                          <div className="max-w-[75%] sm:max-w-[60%]">
                            <div
                              className={`rounded-2xl px-4 py-2 shadow-sm transition-all ${
                                isHighlighted
                                  ? 'ring-2 ring-yellow-400 bg-yellow-50'
                                  : isOwnMessage
                                    ? 'bg-indigo-600 text-white rounded-br-md'
                                    : 'bg-white text-gray-900 rounded-bl-md border border-gray-200'
                              }`}
                            >
                              {!isOwnMessage && showAvatar && message.senderName && (
                                <div className="text-xs font-semibold text-indigo-600 mb-1">
                                  {message.senderName}
                                </div>
                              )}
                              <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">
                                {message.content}
                              </p>
                              <div className={`flex items-center justify-end gap-1 mt-1 text-xs ${isOwnMessage ? 'text-indigo-200' : 'text-gray-500'}`}>
                                <span>{formatMessageTime(message.timestamp)}</span>
                                {isOwnMessage && (
                                  message.read ? <CheckCheck className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                    {isOtherTyping && (
                      <div className="flex items-end gap-2 justify-start">
                        <div className="w-8 h-8" />
                        <div className="bg-white rounded-2xl rounded-bl-md border border-gray-200 px-4 py-3 shadow-sm">
                          <div className="flex gap-1">
                            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                          </div>
                        </div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </>
                )}
              </div>

              {/* Composer */}
              <div className="p-3 bg-gray-100 border-t border-gray-200">
                {showQuickReplies && quickReplies.length > 0 && (
                  <div className="mb-3">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs text-gray-500 font-medium">Quick Replies</p>
                      <button
                        onClick={handleHideQuickReplies}
                        className="text-xs text-gray-400 hover:text-gray-600"
                      >
                        Hide
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {quickReplies.map((reply, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleQuickReplyClick(reply)}
                          className="px-3 py-1.5 bg-white border border-gray-300 rounded-full text-xs text-gray-700 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-600 transition-colors"
                        >
                          {reply}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex items-end gap-2">
                  <textarea
                    ref={textareaRef}
                    value={newMessage}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder="Type a message..."
                    className="flex-1 px-4 py-3 bg-white border border-gray-300 rounded-3xl resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm max-h-32"
                    rows={1}
                    disabled={isSending}
                    maxLength={MAX_MESSAGE_LENGTH}
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
                    {isSending ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                  </button>
                </div>

                <div className="flex items-center justify-between mt-2 px-2">
                  {!showQuickReplies ? (
                    <button
                      onClick={handleShowQuickReplies}
                      className="text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      Show quick replies
                    </button>
                  ) : (
                    <span className="text-xs text-gray-500">Press Enter to send, Shift+Enter for new line</span>
                  )}
                  <span className={`text-xs ${newMessage.length > MAX_MESSAGE_LENGTH * 0.9 ? 'text-amber-600 font-medium' : 'text-gray-400'}`}>
                    {newMessage.length}/{MAX_MESSAGE_LENGTH}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
