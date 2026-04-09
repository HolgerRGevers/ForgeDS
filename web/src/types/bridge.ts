/** Connection state of the bridge WebSocket client. */
export type ConnectionStatus = "connecting" | "connected" | "disconnected";

/** Outbound message sent to the bridge server. */
export interface BridgeMessage {
  id: string;
  type: "refine_prompt" | "build_project" | "lint_check" | "get_status";
  data: Record<string, unknown>;
}

/** Inbound message received from the bridge server. */
export interface BridgeResponse {
  id: string;
  type: "response" | "stream" | "stream_end" | "error";
  data: Record<string, unknown>;
}

/** Zustand store shape for the bridge client. */
export interface BridgeStore {
  status: ConnectionStatus;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
  send: (
    type: string,
    data: Record<string, unknown>,
  ) => Promise<Record<string, unknown>>;
  sendStream: (
    type: string,
    data: Record<string, unknown>,
    onChunk: (chunk: Record<string, unknown>) => void,
  ) => Promise<Record<string, unknown>>;
}

/** Listener callback for connection-state changes. */
export type ConnectionListener = (status: ConnectionStatus) => void;
