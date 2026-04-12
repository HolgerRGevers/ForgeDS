import type {
  BridgeResponse,
  ConnectionListener,
  ConnectionStatus,
} from "../types/bridge";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_TIMEOUT_MS = 30_000;
const STREAM_IDLE_TIMEOUT_MS = 60_000;
const HEARTBEAT_INTERVAL_MS = 30_000;
const HEARTBEAT_STALE_MS = 45_000;

function generateId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return (
    Date.now().toString(36) +
    "-" +
    Math.random().toString(36).substring(2, 10)
  );
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

export class BridgeTimeoutError extends Error {
  constructor(type: string) {
    super(`Bridge request timed out: ${type}`);
    this.name = "BridgeTimeoutError";
  }
}

// ---------------------------------------------------------------------------
// Pending-request bookkeeping
// ---------------------------------------------------------------------------

interface PendingRequest {
  resolve: (data: Record<string, unknown>) => void;
  reject: (err: Error) => void;
  onChunk?: (chunk: Record<string, unknown>) => void;
  timer?: ReturnType<typeof setTimeout>;
}

// ---------------------------------------------------------------------------
// BridgeClient
// ---------------------------------------------------------------------------

const BRIDGE_URL =
  (typeof import.meta !== "undefined" &&
    (import.meta as Record<string, Record<string, string>>).env
      ?.VITE_BRIDGE_URL) ||
  "ws://localhost:9876";
const MAX_BACKOFF_MS = 30_000;

export class BridgeClient {
  private ws: WebSocket | null = null;
  private _status: ConnectionStatus = "disconnected";
  private listeners: Set<ConnectionListener> = new Set();
  private pending: Map<string, PendingRequest> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private backoff = 1000;
  private intentionalClose = false;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private lastPong = 0;

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
    this.stopHeartbeat();
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
   * Times out after `timeoutMs` (default 30s).
   */
  send(
    type: string,
    data: Record<string, unknown>,
    timeoutMs: number = DEFAULT_TIMEOUT_MS,
  ): Promise<Record<string, unknown>> {
    return new Promise((resolve, reject) => {
      if (this._status !== "connected" || !this.ws) {
        reject(new Error("Bridge is not connected"));
        return;
      }

      const id = generateId();

      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new BridgeTimeoutError(type));
      }, timeoutMs);

      this.pending.set(id, { resolve, reject, timer });

      this.ws.send(JSON.stringify({ id, type, data }));
    });
  }

  /**
   * Send a request that returns streaming chunks.
   * `onChunk` is called for every `stream` message.
   * The returned promise resolves with the `stream_end` data.
   * Idle timeout resets on each chunk (default 60s).
   */
  sendStream(
    type: string,
    data: Record<string, unknown>,
    onChunk: (chunk: Record<string, unknown>) => void,
    idleTimeoutMs: number = STREAM_IDLE_TIMEOUT_MS,
  ): Promise<Record<string, unknown>> {
    return new Promise((resolve, reject) => {
      if (this._status !== "connected" || !this.ws) {
        reject(new Error("Bridge is not connected"));
        return;
      }

      const id = generateId();

      const resetTimer = () => {
        const req = this.pending.get(id);
        if (req?.timer) clearTimeout(req.timer);
        const newTimer = setTimeout(() => {
          this.pending.delete(id);
          reject(new BridgeTimeoutError(`${type} (stream idle)`));
        }, idleTimeoutMs);
        if (req) req.timer = newTimer;
      };

      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new BridgeTimeoutError(`${type} (stream idle)`));
      }, idleTimeoutMs);

      this.pending.set(id, {
        resolve,
        reject,
        onChunk: (chunk) => {
          resetTimer();
          onChunk(chunk);
        },
        timer,
      });

      this.ws.send(JSON.stringify({ id, type, data }));
    });
  }

  // -- Internal -------------------------------------------------------------

  private openSocket(): void {
    this.setStatus("connecting");

    const ws = new WebSocket(BRIDGE_URL);

    ws.addEventListener("open", () => {
      this.backoff = 1000;
      this.lastPong = Date.now();
      this.setStatus("connected");
      this.startHeartbeat();
    });

    ws.addEventListener("message", (event) => {
      this.handleMessage(event.data as string);
    });

    ws.addEventListener("close", () => {
      this.ws = null;
      this.stopHeartbeat();
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
      console.warn("[bridge] Received malformed JSON frame");
      return;
    }

    // Handle pong responses to our pings
    if (msg.type === "pong" || msg.type === "error" && msg.id === "__ping__") {
      this.lastPong = Date.now();
      return;
    }

    const req = this.pending.get(msg.id);
    if (!req) return; // no matching request

    switch (msg.type) {
      case "response":
        if (req.timer) clearTimeout(req.timer);
        this.pending.delete(msg.id);
        req.resolve(msg.data);
        break;

      case "stream":
        if (req.onChunk) {
          req.onChunk(msg.data);
        }
        break;

      case "stream_end":
        if (req.timer) clearTimeout(req.timer);
        this.pending.delete(msg.id);
        req.resolve(msg.data);
        break;

      case "error":
        // This correctly handles errors during streaming too
        if (req.timer) clearTimeout(req.timer);
        this.pending.delete(msg.id);
        req.reject(
          new Error(
            (msg.data?.message as string) ?? "Unknown bridge error",
          ),
        );
        break;
    }
  }

  // -- Heartbeat --------------------------------------------------------------

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        // Send a ping; bridge will reply with error (unknown type) which we treat as pong
        this.ws.send(JSON.stringify({ id: "__ping__", type: "ping", data: {} }));

        // Check for stale connection
        if (Date.now() - this.lastPong > HEARTBEAT_STALE_MS) {
          console.warn("[bridge] Connection appears stale, reconnecting");
          this.ws?.close();
        }
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  // -- Reconnect --------------------------------------------------------------

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
    this.pending.forEach((req) => {
      if (req.timer) clearTimeout(req.timer);
      req.reject(new Error(reason));
    });
    this.pending.clear();
  }
}

/** Singleton bridge instance for the whole app. */
export const bridge = new BridgeClient();
