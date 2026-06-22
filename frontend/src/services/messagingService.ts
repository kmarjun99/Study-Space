import { Message, Conversation } from '../types';
import api from './api';

// ============================================================
// Backend → Frontend transformers
// ============================================================

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

// ============================================================
// WebSocket — real-time messaging
// ============================================================

export type MessageEvent =
  | { type: 'NEW_MESSAGE'; payload: Message }
  | { type: 'MESSAGE_READ'; payload: { messageId: string; conversationId: string; readBy: string } }
  | { type: 'CONVERSATION_READ'; payload: { conversationId: string; readBy: string } }
  | { type: 'TYPING'; payload: { conversationId: string; userId: string; isTyping: boolean } };

type MessageListener = (event: MessageEvent) => void;

class MessagingWebSocket {
  private socket: WebSocket | null = null;
  private listeners = new Set<MessageListener>();
  private reconnectTimeout: number | null = null;
  private currentUserId: string | null = null;
  private heartbeatInterval: number | null = null;
  private manuallyDisconnected = false;
  private reconnectAttempts = 0;

  connect(userId: string) {
    if (
      this.socket
      && (
        this.socket.readyState === WebSocket.OPEN
        || this.socket.readyState === WebSocket.CONNECTING
      )
      && this.currentUserId === userId
    ) {
      return; // Already connected for this user
    }
    if (this.currentUserId && this.currentUserId !== userId) {
      this.disconnect();
    }

    this.currentUserId = userId;
    this.manuallyDisconnected = false;
    this.openSocket();
  }

  /**
   * Compute the WebSocket base URL. In order of preference:
   *   1. Runtime API URL injected by env-config.js.
   *   2. VITE_API_BASE_URL build-arg (with http(s) -> ws(s) protocol swap).
   *      Used in dev (points at http://localhost:8000) and in any prod build
   *      that explicitly bakes the backend Cloud Run URL into the bundle.
   *   2. Same-origin fallback derived from window.location. In production
   *      behind a load balancer this gives wss://<your-domain>/ws/... and
   *      relies on the LB routing /ws/* to the backend.
   *   3. Local-dev fallback (http://localhost:8000).
   *
   * The protocol swap is explicit (http -> ws, https -> wss) instead of the
   * old regex with a captured group; that regex silently produced `ws://`
   * for `https://` inputs in some browsers, which then fails the upgrade.
   */
  private resolveWsBaseUrl(): string {
    const runtimeBase = typeof window !== 'undefined'
      ? window.__MYSPACE_RUNTIME_CONFIG__?.API_BASE_URL?.trim()
      : undefined;
    const configuredBase = runtimeBase || import.meta.env.VITE_API_BASE_URL;
    if (configuredBase) {
      const normalized = configuredBase.replace(/\/+$/, '');
      if (normalized.startsWith('https://')) return 'wss://' + normalized.slice('https://'.length);
      if (normalized.startsWith('http://'))  return 'ws://'  + normalized.slice('http://'.length);
      return normalized; // assume the caller already passed ws(s)://
    }
    if (typeof window !== 'undefined' && window.location) {
      const host = window.location.host;
      const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (isLocal) {
        // Local dev — backend on :8000, ws://
        return 'ws://localhost:8000';
      }
      // Production same-origin — LB must route /ws/* to the backend
      const proto = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
      return proto + host;
    }
    return 'ws://localhost:8000';
  }

  private openSocket() {
    if (!this.currentUserId) return;

    const wsBase = this.resolveWsBaseUrl();

    try {
      this.socket = new WebSocket(`${wsBase}/ws/messages/${this.currentUserId}`);
    } catch (err) {
      console.error('[Messaging WS] Failed to construct WebSocket', err);
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      console.log('[Messaging WS] Connected');
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.socket.onmessage = (event) => {
      let raw: any;
      try {
        raw = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!raw || !raw.type) return;

      let normalized: MessageEvent | null = null;
      if (raw.type === 'NEW_MESSAGE') {
        normalized = { type: 'NEW_MESSAGE', payload: transformMessage(raw.payload) };
      } else if (raw.type === 'MESSAGE_READ' || raw.type === 'CONVERSATION_READ' || raw.type === 'TYPING') {
        normalized = { type: raw.type, payload: raw.payload };
      }

      if (normalized) {
        this.listeners.forEach((l) => {
          try { l(normalized!); } catch (err) { console.error('[Messaging WS] listener error', err); }
        });
      }
    };

    this.socket.onclose = () => {
      this.stopHeartbeat();
      this.socket = null;
      if (!this.manuallyDisconnected) this.scheduleReconnect();
    };

    this.socket.onerror = () => {
      // onclose will follow and trigger the reconnect logic
      this.socket?.close();
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimeout) return;
    this.reconnectAttempts += 1;
    const delay = Math.min(30000, 1000 * (2 ** Math.min(this.reconnectAttempts, 5)));
    this.reconnectTimeout = window.setTimeout(() => {
      this.reconnectTimeout = null;
      this.openSocket();
    }, delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    // Send a tiny ping every 30s to keep Cloud Run / proxies from killing the socket
    this.heartbeatInterval = window.setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        try { this.socket.send('ping'); } catch { /* ignore */ }
      }
    }, 30000);
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      window.clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  disconnect() {
    this.manuallyDisconnected = true;
    this.stopHeartbeat();
    if (this.reconnectTimeout) {
      window.clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.socket) {
      try { this.socket.close(); } catch { /* ignore */ }
      this.socket = null;
    }
    this.currentUserId = null;
    this.reconnectAttempts = 0;
  }

  subscribe(listener: MessageListener): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }
}

export const messagingWebSocket = new MessagingWebSocket();

// ============================================================
// REST service
// ============================================================

// Paths use the `/api/messages/*` namespace (the messages router is dual-
// mounted under `/api/` in backend/app/main.py, matching the pattern other
// recent feature routers use). The root `/messages/*` mount is still there
// for backward compatibility — both work, but new code should hit /api so
// production load balancers that only proxy /api/* to the backend keep
// routing correctly. The /messages/* path was hitting the frontend SPA
// fallback (returning index.html) and crashing `.data.map`.
class MessagingService {
  async getConversations(): Promise<Conversation[]> {
    const response = await api.get('/api/messages/conversations');
    // Defensive: if a misconfigured proxy returns HTML (SPA fallback) instead
    // of JSON, axios still hands us response.data as a string. Calling .map
    // on that throws "data.map is not a function" and spams the bg-sync loop.
    // Better to log + return [] so the UI renders the empty state cleanly.
    if (!Array.isArray(response.data)) {
      console.warn('[Messaging] getConversations: backend returned non-array — empty result.', { type: typeof response.data });
      return [];
    }
    return response.data.map(transformConversation);
  }

  async getMessages(conversationId: string, opts?: { limit?: number; before?: string }): Promise<Message[]> {
    const params: Record<string, any> = {};
    if (opts?.limit) params.limit = opts.limit;
    if (opts?.before) params.before = opts.before;
    const response = await api.get(`/api/messages/conversations/${conversationId}/messages`, { params });
    if (!Array.isArray(response.data)) {
      console.warn('[Messaging] getMessages: backend returned non-array — empty result.');
      return [];
    }
    return response.data.map(transformMessage);
  }

  async sendMessage(
    receiverId: string,
    content: string,
    venueId?: string,
    venueType?: string,
  ): Promise<Message> {
    const response = await api.post('/api/messages/send', {
      receiver_id: receiverId,
      content,
      venue_id: venueId,
      venue_type: venueType,
    });
    return transformMessage(response.data);
  }

  async markAsRead(messageId: string): Promise<void> {
    await api.put(`/api/messages/${messageId}/read`);
    window.dispatchEvent(new Event('messagesUpdated'));
  }

  async markConversationAsRead(conversationId: string): Promise<void> {
    await api.put(`/api/messages/conversations/${conversationId}/read`);
    window.dispatchEvent(new Event('messagesUpdated'));
  }

  async getUnreadCount(): Promise<number> {
    try {
      const response = await api.get('/api/messages/unread-count');
      return response.data?.count ?? 0;
    } catch (error) {
      console.error('Failed to fetch unread count:', error);
      return 0;
    }
  }

  async startConversationWithOwner(
    ownerId: string,
    venueId?: string,
    venueType?: string,
  ): Promise<Conversation> {
    const response = await api.post('/api/messages/conversations/start', {
      participant_id: ownerId,
      venue_id: venueId,
      venue_type: venueType,
    });
    window.dispatchEvent(new Event('messagesUpdated'));
    return transformConversation(response.data);
  }

  async sendTyping(receiverId: string, conversationId: string, isTyping = true): Promise<void> {
    try {
      await api.post('/api/messages/typing', {
        receiver_id: receiverId,
        conversation_id: conversationId,
        is_typing: isTyping,
      });
    } catch {
      // Typing is best-effort; silently ignore
    }
  }
}

export const messagingService = new MessagingService();
