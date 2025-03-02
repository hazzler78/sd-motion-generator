'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

export default function Home() {
  const [topic, setTopic] = useState('');
  const [motion, setMotion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    
    try {
      const res = await fetch('http://localhost:8000/api/generate-motion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic }),
      });
      
      if (!res.ok) {
        throw new Error('Något gick fel vid generering av motionen');
      }
      
      const data = await res.json();
      const formattedMotion = data.motion
        .replace(/\n\n+/g, '\n\n')
        .replace(/(\d+)\.(\d+)/g, '$1,$2');
      setMotion(formattedMotion);
    } catch (err) {
      setError(err.message);
      console.error('Error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-sd-light">
      <main className="page-container">
        <header className="page-header">
          <h1 className="text-5xl font-bold text-sd-blue mb-4">
            SD Motion Generator
          </h1>
          <p className="text-xl text-gray-600">
            Generera professionella motioner med AI och statistik
          </p>
        </header>

        <div className="bg-white rounded-lg shadow-lg p-8 mb-8 max-w-2xl mx-auto">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="topic" className="block text-sd-blue font-semibold mb-3 text-center text-xl">
                Ämne för motionen
              </label>
              <input
                id="topic"
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="T.ex. trygghet, skola, äldreomsorg..."
                className="w-full p-4 rounded-lg border-2 border-gray-200 text-sd-blue placeholder-gray-400 
                         focus:outline-none focus:ring-2 focus:ring-sd-yellow focus:border-transparent
                         text-center text-lg"
                disabled={isLoading}
              />
            </div>
            
            <div className="flex justify-center pt-4">
              <button 
                type="submit"
                className="px-12 py-4 bg-sd-yellow text-sd-blue font-bold text-xl rounded-lg
                         hover:opacity-90 transition-all transform hover:-translate-y-0.5
                         disabled:opacity-50 disabled:cursor-not-allowed
                         shadow-md hover:shadow-lg"
                disabled={isLoading || !topic.trim()}
              >
                {isLoading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-6 w-6 text-sd-blue" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Genererar motion...
                  </span>
                ) : 'Generera Motion'}
              </button>
            </div>
          </form>
        </div>

        {error && (
          <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-8 rounded-lg max-w-2xl mx-auto">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-500" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-red-700 font-semibold">{error}</p>
              </div>
            </div>
          </div>
        )}

        {motion && (
          <div className="motion-container">
            <div className="motion-text">
              <ReactMarkdown>{motion}</ReactMarkdown>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
