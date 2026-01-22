import { useState, FormEvent } from 'react'
import { Search, Loader2, BookOpen, FileText } from 'lucide-react'

interface Source {
  title: string;
  path: string;
  page: number;
}

interface Excerpt {
  content: string;
  source: Source;
  relevance_score?: number;
}

interface AskResponse {
  answer: string;
  excerpts: Excerpt[];
  sources: string[];
  total_results?: number;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<AskResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setResponse(null)

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      })

      if (!res.ok) {
        throw new Error('Erreur lors de la requête au serveur')
      }

      const data = await res.json()
      setResponse(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Une erreur est survenue')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <header className="text-center mb-12">
          <h1 className="text-4xl font-extrabold tracking-tight mb-4">
            Assistant Documentaire <span className="text-blue-600">Hybrid</span>
          </h1>
          <p className="text-lg text-gray-600 dark:text-gray-400">
            Recherche intelligente combinant BM25 et Vecteurs par IA.
          </p>
        </header>

        <form onSubmit={handleSearch} className="relative mb-12">
          <div className="relative flex items-center">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 h-5 w-5" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Posez votre question sur les spécifications techniques..."
              className="w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-2xl py-4 pl-12 pr-24 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm leading-tight"
            />
            <button
              type="submit"
              disabled={loading}
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-xl transition disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? <Loader2 className="animate-spin h-4 w-4" /> : 'Rechercher'}
            </button>
          </div>
        </form>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 p-4 rounded-xl mb-8">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center py-20 animate-pulse">
            <Loader2 className="h-12 w-12 text-blue-500 animate-spin mb-4" />
            <p className="text-gray-500 font-medium">Analyse des documents en cours...</p>
          </div>
        )}

        {response && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Answer Section */}
            <section className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-sm border border-gray-100 dark:border-gray-700">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-blue-600" /> Réponse
              </h2>
              <div 
                className="prose dark:prose-invert max-w-none text-gray-700 dark:text-gray-300"
                dangerouslySetInnerHTML={{ __html: response.answer }}
              />
            </section>

            {/* Excerpts Section */}
            <section className="space-y-4">
              <h2 className="text-lg font-bold flex items-center gap-2 px-2">
                <FileText className="h-5 w-5 text-gray-500" /> Extraits pertinents ({response.excerpts.length})
              </h2>
              {response.excerpts.map((exc, idx) => (
                <div key={idx} className="bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700 rounded-xl p-5 shadow-sm hover:border-blue-300 dark:hover:border-blue-900 transition-colors">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-sm text-blue-600 dark:text-blue-400 font-semibold">
                      {exc.source?.path || 'Document'} — Page {exc.source?.page || '?'}
                    </div>
                    {exc.relevance_score !== undefined && (
                      <div className="flex items-center gap-1">
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          Pertinence:
                        </div>
                        <div className={`text-xs font-bold px-2 py-1 rounded ${
                          exc.relevance_score >= 70 ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                          exc.relevance_score >= 40 ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400' :
                          'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                        }`}>
                          {exc.relevance_score.toFixed(0)}%
                        </div>
                      </div>
                    )}
                  </div>
                  <div
                    className="text-gray-600 dark:text-gray-400 text-sm italic"
                    dangerouslySetInnerHTML={{ __html: exc.content }}
                  />
                </div>
              ))}
            </section>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
