import { useState, useCallback, useRef } from "react";
import { ChatMessage, Source } from "../types";

const API_URL = import.meta.env.VITE_API_URL;

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (query: string) => {
      if (!query.trim() || isStreaming) return;

      setError(null);

      // Add user message immediately
      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: query,
        timestamp: Date.now(),
      };

      // Create placeholder assistant message
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        timestamp: Date.now(),
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch(`${API_URL}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query,
            conversation_id: conversationId,
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new Error(`Erreur serveur (${res.status})`);
        }

        const contentType = res.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
          // JSON fallback (no LLM)
          const data = await res.json();
          if (data.conversation_id) setConversationId(data.conversation_id);

          const fallbackContent =
            data.answer +
            (data.excerpts?.length
              ? "\n\n" +
                data.excerpts
                  .map(
                    (e: any) =>
                      `**${e.source.title}** (p.${e.source.page}) — ${e.relevance_score}%\n${e.content}`
                  )
                  .join("\n\n---\n\n")
              : "");

          const sources: Source[] =
            data.excerpts?.map((e: any) => ({
              ...e.source,
              content_preview: e.content?.substring(0, 200),
            })) || [];

          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? {
                    ...m,
                    content: fallbackContent,
                    sources,
                    isStreaming: false,
                  }
                : m
            )
          );
        } else {
          // SSE streaming
          const reader = res.body?.getReader();
          if (!reader) throw new Error("No response body");

          const decoder = new TextDecoder();
          let buffer = "";
          let accContent = "";
          let sources: Source[] = [];

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            let eventType = "";
            for (const line of lines) {
              if (line.startsWith("event: ")) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                const data = line.slice(6);
                try {
                  const parsed = JSON.parse(data);

                  if (eventType === "meta") {
                    setConversationId(parsed.conversation_id);
                  } else if (eventType === "sources") {
                    sources = parsed;
                  } else if (eventType === "token") {
                    accContent += parsed.content;
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsg.id
                          ? { ...m, content: accContent, sources }
                          : m
                      )
                    );
                  } else if (eventType === "done") {
                    // Final update
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsg.id
                          ? {
                              ...m,
                              content: parsed.full_response || accContent,
                              sources,
                              isStreaming: false,
                            }
                          : m
                      )
                    );
                  } else if (eventType === "error") {
                    setError(parsed.error);
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsg.id
                          ? {
                              ...m,
                              content:
                                accContent ||
                                "Une erreur est survenue.",
                              isStreaming: false,
                            }
                          : m
                      )
                    );
                  }
                } catch {
                  // ignore parse errors
                }
                eventType = "";
              }
            }
          }

          // Ensure streaming flag is cleared
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, isStreaming: false }
                : m
            )
          );
        }
      } catch (err: any) {
        if (err.name === "AbortError") {
          // User cancelled
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, isStreaming: false }
                : m
            )
          );
        } else {
          setError(err.message || "Une erreur est survenue");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? {
                    ...m,
                    content: "Erreur de connexion au serveur.",
                    isStreaming: false,
                  }
                : m
            )
          );
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [isStreaming, conversationId]
  );

  const stopGeneration = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const newConversation = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setError(null);
    setIsStreaming(false);
  }, []);

  return {
    messages,
    isStreaming,
    conversationId,
    error,
    sendMessage,
    stopGeneration,
    newConversation,
    setMessages,
    setConversationId,
  };
}
