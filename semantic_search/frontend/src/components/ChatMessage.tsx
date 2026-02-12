import { ChatMessage as ChatMessageType } from "../types";
import { SourceChip } from "./SourceChip";
import { TimingBar } from "./TimingBar";
import { User, Bot, Brain } from "lucide-react";
import { useState } from "react";

interface ChatMessageProps {
  message: ChatMessageType;
}

export const ChatMessageBubble = ({ message }: ChatMessageProps) => {
  const isUser = message.role === "user";
  const [showThinking, setShowThinking] = useState(false);

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""} mb-4`}>
      {/* Avatar */}
      <div
        className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-muted border border-border text-muted-foreground"
        }`}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white rounded-br-md"
            : "bg-muted/50 border border-border text-foreground rounded-bl-md"
        }`}
      >
        {/* Thinking section (collapsible) */}
        {!isUser && message.thinking && (
          <div className="mb-3 pb-3 border-b border-border/50">
            <button
              onClick={() => setShowThinking(!showThinking)}
              className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full text-left"
            >
              <Brain size={14} />
              <span className="font-medium">Réflexion du modèle</span>
              <span className="ml-auto">{showThinking ? "−" : "+"}</span>
            </button>
            {showThinking && (
              <div className="mt-2 p-3 bg-muted/30 rounded-lg text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap border border-border/30">
                {message.thinking}
              </div>
            )}
          </div>
        )}

        {/* Message content */}
        <div className="text-sm leading-relaxed whitespace-pre-wrap break-words chat-prose">
          {message.content}
          {message.isStreaming && (
            <span className="streaming-cursor" />
          )}
        </div>

        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-border/50">
            {message.sources.map((src, i) => (
              <SourceChip key={i} source={src} />
            ))}
          </div>
        )}

        {/* Timings */}
        {!isUser && !message.isStreaming && (message.timings || message.searchMode || message.responseMode) && (
          <div className="mt-3 pt-3 border-t border-border/50">
            <TimingBar
              timings={message.timings}
              searchMode={message.searchMode}
              responseMode={message.responseMode}
              variant="block"
            />
          </div>
        )}
      </div>
    </div>
  );
};
