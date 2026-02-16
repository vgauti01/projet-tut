import { useState, useCallback, useRef } from "react";
import { ChatMessage, Source, SearchTimings } from "../types";

const API_URL = import.meta.env.VITE_API_URL;

// Fonction utilitaire pour extraire le thinking du contenu
function extractThinking(content: string): { thinking: string | undefined; cleanContent: string } {
  const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/);
  if (thinkMatch) {
    const thinking = thinkMatch[1].trim();
    const cleanContent = content.replace(/<think>[\s\S]*?<\/think>/, "").trim();
    return { thinking, cleanContent };
  }
  return { thinking: undefined, cleanContent: content };
}

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
              full_content: e.content, // Stocker le contenu complet
            })) || [];

          const { thinking, cleanContent } = extractThinking(fallbackContent);

          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? {
                    ...m,
                    content: cleanContent,
                    thinking,
                    sources,
                    isStreaming: false,
                    searchMode: data.search_mode,
                    timings: data.timings,
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
          let excerpts: any[] = []; // Stocker les excerpts complets
          let searchMode: string | undefined;
          let timings: SearchTimings | undefined;

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
                  } else if (eventType === "excerpts") {
                    // Stocker les excerpts complets pour utiliser leur contenu entier
                    excerpts = parsed;
                    sources = parsed.map((e: any) => ({
                      ...e.source,
                      content_preview: e.content?.substring(0, 200),
                      full_content: e.content,
                    }));
                  } else if (eventType === "timings") {
                    searchMode = parsed.search_mode;
                    timings = parsed.timings;
                  } else if (eventType === "token") {
                    accContent += parsed.content;
                    const { thinking, cleanContent } = extractThinking(accContent);
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsg.id
                          ? { ...m, content: cleanContent, thinking, sources, searchMode, timings }
                          : m
                      )
                    );
                  } else if (eventType === "done") {
                    // Merge LLM timing into timings
                    const finalTimings: SearchTimings = {
                      ...timings,
                      ...(parsed.llm_ttft_ms !== undefined && { llm_ttft_ms: parsed.llm_ttft_ms }),
                      ...(parsed.llm_total_ms !== undefined && { llm_total_ms: parsed.llm_total_ms }),
                    };
                    const finalContent = parsed.full_response || accContent;
                    const { thinking, cleanContent } = extractThinking(finalContent);
                    
                    // Final update
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantMsg.id
                          ? {
                              ...m,
                              content: cleanContent,
                              thinking,
                              sources,
                              isStreaming: false,
                              searchMode,
                              timings: finalTimings,
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
