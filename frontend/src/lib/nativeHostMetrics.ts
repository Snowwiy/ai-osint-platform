import { useEffect, useState } from "react";

export interface NativeHostMetrics {
  available: boolean;
  source: "native_desktop" | "unavailable";
  cpuPercent: number | null;
  memoryPercent: number | null;
  diskPercent: number | null;
  uptimeSeconds: number | null;
  osName: string | null;
  osVersion: string | null;
  osBuild: string | null;
  hostname: string | null;
  sampledAtUnixMs: number;
  detail: string;
}

type TauriWindow = Window & {
  __TAURI__?: { core?: { invoke: (command: string) => Promise<unknown> } };
};

function isNativeHostMetrics(value: unknown): value is NativeHostMetrics {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<NativeHostMetrics>;
  return (
    typeof item.available === "boolean" &&
    (item.source === "native_desktop" || item.source === "unavailable") &&
    typeof item.sampledAtUnixMs === "number" &&
    typeof item.detail === "string"
  );
}

async function invokeNativeMetrics(): Promise<NativeHostMetrics | null> {
  try {
    const own = (window as TauriWindow).__TAURI__?.core;
    const parent = window.parent !== window ? (window.parent as TauriWindow).__TAURI__?.core : undefined;
    const core = own ?? parent;
    if (!core) return null;
    const value = await core.invoke("get_native_host_metrics");
    return isNativeHostMetrics(value) ? value : null;
  } catch {
    return null;
  }
}

export function useNativeHostMetrics(): NativeHostMetrics | null {
  const [metrics, setMetrics] = useState<NativeHostMetrics | null>(null);
  useEffect(() => {
    const receive = (event: MessageEvent<unknown>) => {
      if (event.source !== window.parent || !event.data || typeof event.data !== "object") return;
      const message = event.data as { type?: unknown; payload?: unknown };
      if (message.type === "raventech-native-host-metrics" && isNativeHostMetrics(message.payload)) {
        setMetrics(message.payload);
      }
    };
    window.addEventListener("message", receive);
    void invokeNativeMetrics().then((value) => value && setMetrics(value));
    return () => window.removeEventListener("message", receive);
  }, []);
  return metrics;
}
