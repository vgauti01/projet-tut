import { useEffect, useRef } from "react";
import { ChatMessageBubble } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { ChatMessage } from "../types";
import { MessageSquare } from "lucide-react";

interface ChatViewProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  onSend: (message: string) => void;
  onStop: () => void;
}

export const ChatView = ({
  messages,
  isStreaming,
  error,
  onSend,
  onStop,
}: ChatViewProps) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="p-4 bg-blue-500/10 rounded-2xl mb-4">
              <MessageSquare size={32} className="text-blue-400" />
            </div>
            <h2 className="text-xl font-semibold text-foreground mb-2">
              Assistant Documentaire
            </h2>
            <p className="text-muted-foreground text-sm max-w-md">
              Posez une question sur vos documents. L'assistant recherchera les
              informations pertinentes et vous fournira une réponse basée sur
              les sources disponibles.
            </p>
            <div className="mt-6 flex gap-2 text-xs text-muted-foreground/60">
              <span className="bg-muted px-2 py-1 rounded-md border border-border">
                BM25
              </span>
              <span>+</span>
              <span className="bg-muted px-2 py-1 rounded-md border border-border">
                Vecteurs
              </span>
              <span>+</span>
              <span className="bg-muted px-2 py-1 rounded-md border border-border">
                Cross-Encoder
              </span>
              <span>+</span>
              <span className="bg-muted px-2 py-1 rounded-md border border-border">
                LLM
              </span>
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto">
            {messages.map((msg) => (
              <ChatMessageBubble key={msg.id} message={msg} />
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="max-w-3xl mx-auto mt-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput
        onSend={onSend}
        onStop={onStop}
        isStreaming={isStreaming}
      />
    </div>
  );
};
