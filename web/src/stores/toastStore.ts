import { create } from "zustand";

export type ToastType = "success" | "error" | "info";
export type ToastPosition = "bottom-right" | "top-center";

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  position: ToastPosition;
  duration: number; // ms, 0 = manual dismiss
}

interface ToastState {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => string;
  removeToast: (id: string) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
}

let nextId = 0;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],

  addToast: (toast) => {
    const id = `toast-${++nextId}`;
    set({ toasts: [...get().toasts, { ...toast, id }] });

    if (toast.duration > 0) {
      setTimeout(() => get().removeToast(id), toast.duration);
    }

    return id;
  },

  removeToast: (id) => {
    set({ toasts: get().toasts.filter((t) => t.id !== id) });
  },

  success: (title, message) => {
    get().addToast({
      type: "success",
      title,
      message,
      position: "bottom-right",
      duration: 5000,
    });
  },

  error: (title, message) => {
    get().addToast({
      type: "error",
      title,
      message,
      position: "top-center",
      duration: 0, // Errors stay until dismissed
    });
  },

  info: (title, message) => {
    get().addToast({
      type: "info",
      title,
      message,
      position: "bottom-right",
      duration: 4000,
    });
  },
}));
