import { useState, useCallback, useEffect } from "react";
import { ChatSession, ChatMessage } from "../types";

const STORAGE_KEY = "chat_sessions";
const MAX_SESSIONS = 50;

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function persistSessions(sessions: ChatSession[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)));
}

export function useSessions() {
  const [sessions, setSessions] = useState<ChatSession[]>(loadSessions);

  useEffect(() => {
    persistSessions(sessions);
  }, [sessions]);

  const saveSession = useCallback(
    (id: string, messages: ChatMessage[]) => {
      if (messages.length === 0) return;

      const firstUserMsg = messages.find((m) => m.role === "user");
      const title = firstUserMsg
        ? firstUserMsg.content.slice(0, 60) + (firstUserMsg.content.length > 60 ? "..." : "")
        : "Nouvelle conversation";

      setSessions((prev) => {
        const existing = prev.findIndex((s) => s.id === id);
        const session: ChatSession = {
          id,
          title,
          messages,
          createdAt: existing >= 0 ? prev[existing].createdAt : Date.now(),
          updatedAt: Date.now(),
        };

        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = session;
          return updated;
        }
        return [session, ...prev].slice(0, MAX_SESSIONS);
      });
    },
    []
  );

  const deleteSession = useCallback((id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const getSession = useCallback(
    (id: string) => sessions.find((s) => s.id === id) || null,
    [sessions]
  );

  return { sessions, saveSession, deleteSession, getSession };
}
