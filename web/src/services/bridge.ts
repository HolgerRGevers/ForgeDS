import type {
  BridgeResponse,
  ConnectionListener,
  ConnectionStatus,
} from "../types/bridge";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function generateId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID
  return (
    Date.now().toString(36) +
    "-" +
    Math.random().toString(36).substring(2, 10)
  );
}

// ---------------------------------------------------------------------------
// Pending-request bookkeeping
// ---------------------------------------------------------------------------

interface PendingRequest {
  resolve: (data: Record<string, unknown>) => void;
  reject: (err: Error) => void;
  onChunk?: (chunk: Record<string, unknown>) => void;
}

// ---------------------------------------------------------------------------
// BridgeClient
// ---------------------------------------------------------------------------

const BRIDGE_URL = "ws://localhost:9876";
const MAX_BACKOFF_MS = 30_000;

export class BridgeClient {
  private ws: WebSocket | null = null;
  private _status: ConnectionStatus = "disconnected";
  private listeners: Set<ConnectionListener> = new Set();
  private pending: Map<string, PendingRequest> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private backoff = 1000;
  private intentionalClose = false;

  // -- Connection state -----------------------------------------------------

  get status(): ConnectionStatus {
    return this._status;
  }

  private setStatus(next: ConnectionStatus) {
    if (this._status === next) return;
    this._status = next;
    this.listeners.forEach((fn) => fn(next));
  }

  /** Register a listener for connection-status changes. Returns an unsubscribe function. */
  onStatusChange(fn: ConnectionListener): () => void {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  }

  // -- Connect / disconnect -------------------------------------------------

  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return; // already active
    }
    this.intentionalClose = false;
    this.openSocket();
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnect();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.rejectAll("Disconnected by client");
    this.setStatus("disconnected");
  }

  // -- Messaging ------------------------------------------------------------

  /**
   * Send a single request and wait for the matching `response` or `error`.
   */
  send(
    type: string,
    data: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    return new Promise((resolve, reject) => {
      if (this._status !== "connected" || !this.ws) {
        reject(new Error("Bridge is not connected"));
        return;
      }

      const id = generateId();
      this.pending.set(id, { resolve, reject });

      this.ws.send(JSON.stringify({ id, type, data }));
    });
  }

  /**
   * Send a request that returns streaming chunks.
   * `onChunk` is called for every `stream` message.
   * The returned promise resolves with the `stream_end` data.
   */
  sendStream(
    type: string,
    data: Record<string, unknown>,
    onChunk: (chunk: Record<string, unknown>) => void,
  ): Promise<Record<string, unknown>> {
    return new Promise((resolve, reject) => {
      if (this._status !== "connected" || !this.ws) {
        reject(new Error("Bridge is not connected"));
        return;
      }

      const id = generateId();
      this.pending.set(id, { resolve, reject, onChunk });

      this.ws.send(JSON.stringify({ id, type, data }));
    });
  }

  // -- Internal -------------------------------------------------------------

  private openSocket(): void {
    this.setStatus("connecting");

    const ws = new WebSocket(BRIDGE_URL);

    ws.addEventListener("open", () => {
      this.backoff = 1000;
      this.setStatus("connected");
    });

    ws.addEventListener("message", (event) => {
      this.handleMessage(event.data as string);
    });

    ws.addEventListener("close", () => {
      this.ws = null;
      this.setStatus("disconnected");
      if (!this.intentionalClose) {
        this.scheduleReconnect();
      }
    });

    ws.addEventListener("error", () => {
      // The close event will fire after this, which handles state + reconnect.
    });

    this.ws = ws;
  }

  private handleMessage(raw: string): void {
    let msg: BridgeResponse;
    try {
      msg = JSON.parse(raw) as BridgeResponse;
    } catch {
      return; // ignore malformed frames
    }

    const req = this.pending.get(msg.id);
    if (!req) return; // no matching request

    switch (msg.type) {
      case "response":
        this.pending.delete(msg.id);
        req.resolve(msg.data);
        break;

      case "stream":
        if (req.onChunk) {
          req.onChunk(msg.data);
        }
        break;

      case "stream_end":
        this.pending.delete(msg.id);
        req.resolve(msg.data);
        break;

      case "error":
        this.pending.delete(msg.id);
        req.reject(
          new Error(
            (msg.data?.message as string) ?? "Unknown bridge error",
          ),
        );
        break;
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnect();
    this.reconnectTimer = setTimeout(() => {
      this.openSocket();
    }, this.backoff);
    this.backoff = Math.min(this.backoff * 2, MAX_BACKOFF_MS);
  }

  private clearReconnect(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private rejectAll(reason: string): void {
    this.pending.forEach((req) => req.reject(new Error(reason)));
    this.pending.clear();
  }
}

/** Singleton bridge instance for the whole app. */
export const bridge = new BridgeClient();
