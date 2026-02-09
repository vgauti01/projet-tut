export interface Source {
  title: string;
  page: number;
  path: string;
  score: number;
  source_type?: string;
  content_preview?: string;
}

export interface Excerpt {
  content: string;
  source: Source;
  relevance_score: number;
}

export interface SearchResponse {
  answer: string;
  excerpts: Excerpt[];
  sources: string[];
  total_results: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  timestamp: number;
  isStreaming?: boolean;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

export type AppMode = "search" | "chat";

// SSE event types
export interface SSEMetaEvent {
  conversation_id: string;
}

export interface SSESourcesEvent extends Array<Source> {}

export interface SSETokenEvent {
  content: string;
}

export interface SSEDoneEvent {
  full_response: string;
}

export interface SSEErrorEvent {
  error: string;
}
