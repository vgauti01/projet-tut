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

export interface SearchTimings {
  meilisearch_ms?: number;
  qdrant_ms?: number;
  rrf_fusion_ms?: number;
  reranking_ms?: number;
  llm_ttft_ms?: number;
  llm_total_ms?: number;
}

export interface SearchResponse {
  answer: string;
  excerpts: Excerpt[];
  sources: string[];
  total_results: number;
  search_mode?: string;
  timings?: SearchTimings;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  timestamp: number;
  isStreaming?: boolean;
  searchMode?: string;
  timings?: SearchTimings;
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
  llm_ttft_ms?: number;
  llm_total_ms?: number;
}

export interface SSETimingsEvent {
  search_mode: string;
  timings: SearchTimings;
}

export interface SSEErrorEvent {
  error: string;
}
