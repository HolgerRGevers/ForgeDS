import { create } from "zustand";
import { bridge } from "../services/bridge";
import type { BridgeStore } from "../types/bridge";

export const useBridgeStore = create<BridgeStore>((set) => {
  // Keep Zustand in sync with the raw client's connection state.
  bridge.onStatusChange((status) => {
    set({ status });
  });

  return {
    status: bridge.status,
    error: null,

    connect: () => {
      set({ error: null });
      bridge.connect();
    },

    disconnect: () => {
      bridge.disconnect();
    },

    send: async (type, data) => {
      try {
        return await bridge.send(type, data);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Unknown error";
        set({ error: message });
        throw err;
      }
    },

    sendStream: async (type, data, onChunk) => {
      try {
        return await bridge.sendStream(type, data, onChunk);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Unknown error";
        set({ error: message });
        throw err;
      }
    },
  };
});
