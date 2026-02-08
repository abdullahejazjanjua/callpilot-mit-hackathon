import { useState, useCallback } from "react";
import { useConversation } from "@elevenlabs/react";
import LoadingScreen from "@/components/LoadingScreen";
import HeroSection from "@/components/HeroSection";
import StatusTerminal from "@/components/StatusTerminal";
import { useEventStream } from "@/hooks/use-event-stream";
import { getSignedUrl } from "@/lib/api";

const Index = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);

  const handleLoaded = useCallback(() => setIsLoading(false), []);

  // ── SSE event stream (always on once past loading) ────
  const { logs, connected, addLog, clearLogs } = useEventStream(!isLoading);

  // ── ElevenLabs conversation ───────────────────────────
  const conversation = useConversation({
    onConnect: () => {
      setIsConnecting(false);
      addLog("Voice agent connected — speak naturally", "success", "agent");
    },
    onDisconnect: () => {
      addLog("Voice agent disconnected", "system", "agent");
    },
    onMessage: (msg) => {
      // IncomingSocketEvent: user_transcript | agent_response | client_tool_call | etc.
      const event = msg as Record<string, unknown>;
      if (event.type === "user_transcript") {
        const transcript = (event.user_transcription_event as Record<string, string>)
          ?.user_transcript;
        if (transcript) addLog(`You: ${transcript}`, "info", "agent");
      } else if (event.type === "agent_response") {
        const response = (event.agent_response_event as Record<string, string>)
          ?.agent_response;
        if (response) addLog(`Agent: ${response}`, "info", "agent");
      } else if (event.type === "client_tool_call") {
        const toolCall = event.client_tool_call as Record<string, string>;
        if (toolCall?.tool_name) {
          addLog(`Tool call: ${toolCall.tool_name}`, "warning", "agent");
        }
      }
    },
    onError: (err) => {
      setIsConnecting(false);
      addLog(`Voice error: ${String(err)}`, "error", "agent");
    },
  });

  const isActive = conversation.status === "connected";

  const handleToggle = async () => {
    if (isActive) {
      await conversation.endSession();
      return;
    }

    setIsConnecting(true);
    clearLogs();
    addLog("Requesting voice session...", "system", "agent");

    try {
      // Try getting a signed URL from the backend first
      const signedUrl = await getSignedUrl();
      await conversation.startSession({ signedUrl });
    } catch (err) {
      // If signed URL fails, try with agent ID from env
      const agentId = import.meta.env.VITE_ELEVENLABS_AGENT_ID;
      if (agentId) {
        try {
          addLog("Signed URL unavailable, using agent ID directly", "warning", "agent");
          await conversation.startSession({
            agentId,
            connectionType: "websocket",
          });
        } catch (innerErr) {
          setIsConnecting(false);
          addLog(
            `Failed to connect: ${innerErr instanceof Error ? innerErr.message : "Unknown error"}`,
            "error",
            "agent"
          );
        }
      } else {
        setIsConnecting(false);
        addLog(
          `Connection failed: ${err instanceof Error ? err.message : "Check backend is running"}`,
          "error",
          "agent"
        );
      }
    }
  };

  return (
    <>
      {isLoading && <LoadingScreen onLoaded={handleLoaded} />}

      <div
        className={`min-h-screen bg-background flex flex-col transition-opacity duration-500 ${
          isLoading ? "opacity-0" : "opacity-100"
        }`}
      >
        <HeroSection
          isActive={isActive}
          isConnecting={isConnecting}
          onToggle={handleToggle}
        />

        <div className="px-4 pb-16">
          <StatusTerminal
            isActive={isActive || logs.length > 0}
            connected={connected}
            logs={logs}
          />
        </div>
      </div>
    </>
  );
};

export default Index;
