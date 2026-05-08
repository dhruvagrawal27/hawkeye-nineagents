/**
 * Singleton WebSocket connection for live alerts + replay events.
 * Auto-reconnects with exponential backoff. Subscribers register a callback.
 */

export type WsMessage =
  | { type: 'alert.new'; alert: any }
  | { type: 'replay.status'; status: string; stats?: any }
  | { type: string; [key: string]: any };

type Listener = (msg: WsMessage) => void;

class HawkeyeWebSocket {
  private socket: WebSocket | null = null;
  private listeners: Set<Listener> = new Set();
  private reconnectDelay = 1_000;
  private url: string;
  private closing = false;

  constructor(url?: string) {
    const base = (import.meta.env.VITE_WS_BASE_URL as string) || '/ws';
    this.url = url ?? this.absoluteWsUrl(`${base}/alerts`);
  }

  private absoluteWsUrl(path: string): string {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}${path}`;
  }

  connect() {
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) return;
    this.closing = false;
    try {
      this.socket = new WebSocket(this.url);
    } catch (e) {
      console.warn('[ws] construct failed', e);
      this.scheduleReconnect();
      return;
    }
    this.socket.onopen = () => {
      this.reconnectDelay = 1_000;
    };
    this.socket.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        this.listeners.forEach((cb) => cb(msg));
      } catch {
        /* ignore */
      }
    };
    this.socket.onclose = () => {
      if (!this.closing) this.scheduleReconnect();
    };
    this.socket.onerror = () => {
      this.socket?.close();
    };
  }

  disconnect() {
    this.closing = true;
    this.socket?.close();
    this.socket = null;
  }

  subscribe(cb: Listener): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  private scheduleReconnect() {
    const delay = Math.min(this.reconnectDelay, 15_000);
    setTimeout(() => {
      this.reconnectDelay = Math.min(this.reconnectDelay * 1.6, 15_000);
      this.connect();
    }, delay);
  }
}

export const hawkeyeWs = new HawkeyeWebSocket();
