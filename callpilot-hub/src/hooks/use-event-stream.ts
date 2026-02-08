/**
 * SSE hook — connects to the backend /events/stream endpoint
 * and feeds real-time log entries to the StatusTerminal.
 */

import { useEffect, useRef, useCallback, useState } from "react";
import { getEventStreamUrl } from "@/lib/api";

export interface LogEntry {
  id: number;
  timestamp: string;
  type: "info" | "success" | "warning" | "error" | "system";
  message: string;
  source?: string;
}

export function useEventStream(enabled: boolean) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const nextId = useRef(1);
  const esRef = useRef<EventSource | null>(null);

  const addLog = useCallback(
    (message: string, type: LogEntry["type"] = "info", source?: string) => {
      const entry: LogEntry = {
        id: nextId.current++,
        timestamp: new Date().toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        type,
        message,
        source,
      };
      setLogs((prev) => [...prev.slice(-50), entry]); // Keep last 50
    },
    []
  );

  const clearLogs = useCallback(() => {
    setLogs([]);
    nextId.current = 1;
  }, []);

  useEffect(() => {
    if (!enabled) {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
        setConnected(false);
      }
      return;
    }

    const url = getEventStreamUrl();
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      addLog("Connected to CallPilot backend", "system", "system");
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        addLog(data.message, data.type, data.source);
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      setConnected(false);
      // EventSource auto-reconnects
    };

    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, [enabled, addLog]);

  return { logs, connected, addLog, clearLogs };
}
