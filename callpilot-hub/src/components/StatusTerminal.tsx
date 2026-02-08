import { useEffect, useRef } from "react";
import { Terminal } from "lucide-react";
import type { LogEntry } from "@/hooks/use-event-stream";

const IDLE_LOGS: LogEntry[] = [
  {
    id: 0,
    timestamp: "—",
    type: "system",
    message: "Ready for instruction.",
  },
];

const typeColorMap: Record<LogEntry["type"], string> = {
  info: "text-terminal-foreground",
  success: "text-terminal-success",
  warning: "text-terminal-warning",
  error: "text-terminal-error",
  system: "text-terminal-muted",
};

const typePrefixMap: Record<LogEntry["type"], string> = {
  info: "INFO",
  success: " OK ",
  warning: "WARN",
  error: " ERR",
  system: " SYS",
};

interface StatusTerminalProps {
  isActive: boolean;
  connected: boolean;
  logs: LogEntry[];
}

const StatusTerminal = ({ isActive, connected, logs }: StatusTerminalProps) => {
  const bodyRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [logs]);

  const displayedLogs = isActive && logs.length > 0 ? logs : IDLE_LOGS;

  return (
    <div className="w-full max-w-3xl mx-auto">
      {/* Terminal header */}
      <div className="flex items-center gap-2 px-4 py-3 bg-secondary rounded-t-lg border border-border border-b-0">
        <Terminal className="w-4 h-4 text-primary" />
        <span className="text-sm font-medium text-foreground">Live Status Terminal</span>
        <div className="ml-auto flex items-center gap-1.5">
          <span
            className={`w-2.5 h-2.5 rounded-full transition-colors duration-500 ${
              connected
                ? "bg-terminal-success animate-pulse"
                : isActive
                ? "bg-terminal-warning animate-pulse"
                : "bg-terminal-muted"
            }`}
          />
          <span className="text-xs text-muted-foreground">
            {connected ? "CONNECTED" : isActive ? "CONNECTING" : "STANDBY"}
          </span>
        </div>
      </div>

      {/* Terminal body */}
      <div
        ref={bodyRef}
        className="bg-terminal rounded-b-lg border border-border p-4 min-h-[200px] max-h-[300px] overflow-y-auto terminal-scrollbar font-mono text-sm"
      >
        {displayedLogs.map((log) => (
          <div
            key={log.id}
            className="flex gap-3 py-1 animate-log-enter"
          >
            <span className="text-terminal-muted shrink-0">{log.timestamp}</span>
            <span
              className={`shrink-0 ${typeColorMap[log.type]}`}
            >
              [{typePrefixMap[log.type]}]
            </span>
            <span className={typeColorMap[log.type]}>{log.message}</span>
          </div>
        ))}

        {/* Blinking cursor */}
        <div className="flex items-center gap-1 py-1 mt-1">
          <span className="text-primary animate-terminal-blink">▌</span>
        </div>
      </div>
    </div>
  );
};

export default StatusTerminal;
