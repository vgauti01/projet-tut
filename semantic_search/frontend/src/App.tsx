import { useState } from "react";
import { SearchBar } from "./components/SearchBar";
import { ResultCard } from "./components/ResultCard";
import { AlertCircle, Sparkles } from "lucide-react";

interface SearchResponse {
  answer: string;
  excerpts: any[];
  sources: string[];
  total_results: number;
}

function App() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");

  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError("");
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
    } catch (err) {
      setError("An error occurred while fetching results. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center p-4 sm:p-8 font-sans">
      
      {/* Top Decoration */}
      <div className="fixed top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 via-purple-500 to-blue-600 opacity-50" />

      {/* Main Search Area */}
      <div className="w-full max-w-5xl z-10 mt-[10vh]">
        <SearchBar
          value={query}
          onChange={setQuery}
          onSearch={handleSearch}
          loading={loading}
          hasResults={!!results || loading} // Keep top position if loading
        />
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-8 p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 flex items-center gap-2 max-w-lg animate-in fade-in slide-in-from-bottom-2">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Loading Skeletons */}
      {loading && (
        <div className="w-full max-w-4xl mt-12 grid gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-muted/20 rounded-xl animate-pulse border border-border/50" />
          ))}
        </div>
      )}

      {/* Results Display */}
      {results && !loading && (
        <div className="w-full max-w-4xl mt-12 animate-in fade-in slide-in-from-bottom-4 duration-700">
          
          <div className="flex items-center gap-2 mb-6 text-blue-400 font-medium px-1">
            <Sparkles size={16} />
            <span>AI Insights found in {results.sources.length} documents</span>
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
  );
}

export default App;