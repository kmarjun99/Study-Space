
import { CabinStatus } from '../types';

export interface RealTimeEvent {
  type: 'CABIN_UPDATE';
  payload: {
    cabinId: string;
    status: CabinStatus;
  };
}

type Listener = (event: RealTimeEvent) => void;

// Feature flag - set to true when WebSocket backend is implemented
const WEBSOCKET_ENABLED = false;

class RealTimeService {
  private listeners: Listener[] = [];
  private socket: WebSocket | null = null;
  private reconnectTimeout: number | null = null;
  private hasConnected = false;

  constructor() {
    // Don't auto-connect - wait for explicit connect() or first subscriber
    if (WEBSOCKET_ENABLED) {
      this.connect();
    }
  }

  private connect() {
    if (!WEBSOCKET_ENABLED || this.hasConnected) return;

    try {
      this.socket = new WebSocket('ws://localhost:8000/ws/cabins');
      this.hasConnected = true;

      this.socket.onopen = () => {
        console.log('Connected to WebSocket');
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'CABIN_UPDATE') {
            this.notify(data);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message', err);
        }
      };

      this.socket.onclose = () => {
        this.socket = null;
        // Only reconnect if WebSocket is enabled
        if (WEBSOCKET_ENABLED && this.listeners.length > 0) {
          this.reconnectTimeout = window.setTimeout(() => this.connect(), 5000);
        }
      };

      this.socket.onerror = () => {
        // Silently handle - don't spam console
        if (this.socket) {
          this.socket.close();
        }
      };
    } catch (err) {
      // WebSocket not available - silently fail
    }
  }

  subscribe(listener: Listener) {
    this.listeners.push(listener);
    // Lazy connect when first subscriber
    if (WEBSOCKET_ENABLED && !this.socket) {
      this.connect();
    }
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify(event: RealTimeEvent) {
    this.listeners.forEach(l => l(event));
  }
}

export const realTimeService = new RealTimeService();
