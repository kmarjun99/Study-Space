import React, { useState } from 'react';
import { getLocationInsights, AIResponse } from '../services/aiService';
import { Button, Card, Input } from './UI';
import { MapPin, Send, Sparkles, ExternalLink, Navigation } from 'lucide-react';

interface LocationScoutProps {
  contextAddress?: string;
  contextName?: string;
  className?: string;
}

export const LocationScout: React.FC<LocationScoutProps> = ({ contextAddress, contextName, className = '' }) => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<AIResponse | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setResult(null);
    
    const response = await getLocationInsights(query, contextAddress);
    
    setResult(response);
    setIsLoading(false);
  };

  const suggestedQueries = [
    "What public transport is nearby?",
    "Are there affordable restaurants around?",
    "Is there a park or gym nearby?",
    "How far is the nearest metro station?"
  ];

  if (!isOpen) {
    return (
      <button 
        onClick={() => setIsOpen(true)}
        className={`flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-4 py-2 rounded-full shadow-lg hover:shadow-xl transition-all transform hover:-translate-y-0.5 text-sm font-medium ${className}`}
      >
        <Sparkles className="w-4 h-4" />
        {contextName ? `Ask about ${contextName}` : "Ask Location Scout"}
      </button>
    );
  }

  return (
    <Card className={`border-indigo-100 shadow-xl overflow-hidden flex flex-col ${className}`}>
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 p-4 flex justify-between items-center">
        <div className="flex items-center gap-2 text-white">
          <div className="p-1.5 bg-white/20 rounded-lg backdrop-blur-sm">
            <Navigation className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-sm">Location Scout</h3>
            {contextName && <p className="text-xs text-indigo-100 opacity-90">Focus: {contextName}</p>}
          </div>
        </div>
        <button 
          onClick={() => setIsOpen(false)}
          className="text-white/80 hover:text-white text-xs font-medium bg-white/10 px-2 py-1 rounded hover:bg-white/20"
        >
          Close
        </button>
      </div>

      <div className="p-4 bg-indigo-50/30 flex-1 max-h-[400px] overflow-y-auto custom-scrollbar">
        {!result && !isLoading && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              I can use Google Maps to check the area around {contextAddress ? "this venue" : "your location"}. What would you like to know?
            </p>
            <div className="flex flex-wrap gap-2">
              {suggestedQueries.map(q => (
                <button
                  key={q}
                  onClick={() => setQuery(q)}
                  className="text-xs bg-white border border-indigo-100 text-indigo-700 px-3 py-1.5 rounded-full hover:bg-indigo-50 hover:border-indigo-200 transition-colors text-left"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {isLoading && (
          <div className="flex flex-col items-center justify-center py-8 space-y-3">
            <div className="w-8 h-8 border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
            <p className="text-xs text-indigo-500 font-medium animate-pulse">Consulting Google Maps...</p>
          </div>
        )}

        {result && (
          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2">
            <div className="bg-white p-3 rounded-lg border border-indigo-50 shadow-sm">
              <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{result.text}</p>
            </div>

            {/* Google Maps Sources */}
            {result.groundingChunks.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1">
                   <MapPin className="w-3 h-3" /> Sources
                </h4>
                <div className="grid gap-2">
                  {result.groundingChunks.map((chunk, idx) => {
                    const mapData = chunk.maps;
                    if (!mapData) return null;
                    return (
                      <a 
                        key={idx}
                        href={mapData.uri}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 p-2 bg-white border border-gray-200 rounded-lg hover:border-indigo-300 hover:shadow-sm transition-all group"
                      >
                        <div className="bg-green-100 p-1.5 rounded text-green-700">
                          <MapPin className="w-4 h-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate group-hover:text-indigo-600">
                            {mapData.title}
                          </p>
                          <p className="text-xs text-gray-500 flex items-center">
                            View on Google Maps <ExternalLink className="w-3 h-3 ml-1 opacity-50" />
                          </p>
                        </div>
                      </a>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <form onSubmit={handleSearch} className="p-3 bg-white border-t border-gray-100">
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about this location..."
            className="w-full pl-4 pr-10 py-2.5 bg-gray-50 border border-gray-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
          />
          <button 
            type="submit"
            disabled={!query.trim() || isLoading}
            className="absolute right-1.5 top-1.5 p-1.5 bg-indigo-600 text-white rounded-full disabled:opacity-50 disabled:cursor-not-allowed hover:bg-indigo-700 transition-colors"
          >
            <Send className="w-3 h-3" />
          </button>
        </div>
      </form>
    </Card>
  );
};