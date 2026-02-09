import { useState, useEffect } from "react";
import { SearchBar } from "./components/SearchBar";
import { ResultCard } from "./components/ResultCard";
import { ChatView } from "./components/ChatView";
import { Sidebar } from "./components/Sidebar";
import { ModeSwitcher } from "./components/ModeSwitcher";
import { useChat } from "./hooks/useChat";
import { useSessions } from "./hooks/useSessions";
import { AlertCircle, Sparkles, Menu } from "lucide-react";
import { AppMode, SearchResponse, ChatSession } from "./types";

function App() {
  const [mode, setMode] = useState<AppMode>("chat");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Search mode state
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [searchError, setSearchError] = useState("");

  // Chat
  const {
    messages,
    isStreaming,
    conversationId,
    error: chatError,
    sendMessage,
    stopGeneration,
    newConversation,
    setMessages,
    setConversationId,
  } = useChat();

  // Sessions
  const { sessions, saveSession, deleteSession } = useSessions();

  // Persist chat session when messages change
  useEffect(() => {
    if (conversationId && messages.length > 0) {
      saveSession(conversationId, messages);
    }
  }, [messages, conversationId, saveSession]);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setSearchError("");
    setResults(null);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) throw new Error("Search service unreachable");

      const data = await response.json();
      setResults(data);
    } catch {
      setSearchError("An error occurred while fetching results. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    newConversation();
    setSidebarOpen(false);
  };

  const handleSelectSession = (session: ChatSession) => {
    setMessages(session.messages);
    setConversationId(session.id);
    setSidebarOpen(false);
  };

  const handleDeleteSession = (id: string) => {
    deleteSession(id);
    if (conversationId === id) {
      newConversation();
    }
  };

  return (
    <div className="h-screen flex bg-background text-foreground font-sans overflow-hidden">
      {/* Top gradient bar */}
      <div className="fixed top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 via-purple-500 to-blue-600 opacity-50 z-50" />

      {/* Sidebar (chat mode only) */}
      {mode === "chat" && (
        <Sidebar
          sessions={sessions}
          activeSessionId={conversationId}
          onNewChat={handleNewChat}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
        />
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-border bg-background/80 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            {mode === "chat" && (
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="lg:hidden p-2 hover:bg-muted rounded-lg transition-colors"
              >
                <Menu size={18} />
              </button>
            )}
            <h1 className="text-sm font-semibold text-foreground/80">
              Hybrid Knowledge Base
            </h1>
          </div>
          <ModeSwitcher mode={mode} onChange={setMode} />
        </header>

        {/* Content */}
        {mode === "chat" ? (
          <ChatView
            messages={messages}
            isStreaming={isStreaming}
            error={chatError}
            onSend={sendMessage}
            onStop={stopGeneration}
          />
        ) : (
          <div className="flex-1 overflow-y-auto flex flex-col items-center p-4 sm:p-8">
            <div className="w-full max-w-5xl mt-[5vh]">
              <SearchBar
                value={query}
                onChange={setQuery}
                onSearch={handleSearch}
                loading={loading}
                hasResults={!!results || loading}
              />
            </div>

            {searchError && (
              <div className="mt-8 p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 flex items-center gap-2 max-w-lg animate-in fade-in slide-in-from-bottom-2">
                <AlertCircle size={18} />
                <span>{searchError}</span>
              </div>
            )}

            {loading && (
              <div className="w-full max-w-4xl mt-12 grid gap-4">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-32 bg-muted/20 rounded-xl animate-pulse border border-border/50"
                  />
                ))}
              </div>
            )}

            {results && !loading && (
              <div className="w-full max-w-4xl mt-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
                <div className="flex items-center gap-2 mb-6 text-blue-400 font-medium px-1">
                  <Sparkles size={16} />
                  <span>
                    AI Insights found in {results.sources.length} documents
                  </span>
                </div>

                <div className="grid gap-4">
                  {results.excerpts.map((excerpt, i) => (
                    <ResultCard key={i} excerpt={excerpt} index={i} />
                  ))}
                </div>

                <div className="mt-12 text-center text-muted-foreground text-sm pb-8">
                  <p>End of results</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
