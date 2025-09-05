import React, { useState, useRef, useEffect } from 'react';
import MermaidDiagram from '@/lib/mermaid';

interface Tool {
  name: string;
  status: 'running' | 'complete';
  args?: any;
  output?: any;
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  tools?: Tool[];
  diagrams?: string[];
}

interface BackendStatus {
  file_count: number;
  decision_backend: string;
  using_vvs: boolean;
  policy_reasons?: string[];
  chunk_count?: number;
  backend_type?: string;
  environment?: {
    VVS_FORCE: string;
    VVS_ENABLED: string;
    GCP_PROJECT_ID: boolean;
  };
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [backendStatus, setBackendStatus] = useState<BackendStatus | null>(null);
  const [sessionId] = useState(() => `session-${Date.now()}`);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const strictModeGuard = useRef(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  const fetchBackendStatus = async () => {
    try {
      const response = await fetch('/api/backend/status');
      if (response.ok) {
        const status = await response.json();
        setBackendStatus(status);
      }
    } catch (error) {
      console.error('Failed to fetch backend status:', error);
    }
  };

  const sendMessage = () => {
    if (!input.trim() || isStreaming) return;

    // Guard against React StrictMode double-execution
    if (strictModeGuard.current) return;
    strictModeGuard.current = true;
    setTimeout(() => { strictModeGuard.current = false; }, 100);

    const userMessage = input.trim();
    setInput('');
    setIsStreaming(true);

    // Close any existing EventSource
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

    // Create assistant message placeholder
    const assistantMessage: Message = { role: 'assistant', content: '', tools: [], diagrams: [] };
    setMessages(prev => [...prev, assistantMessage]);

    // Create EventSource for SSE
    const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
    const params = new URLSearchParams({
      message: userMessage,
      session_id: sessionId
    });
    
    const eventSource = new EventSource(`${apiBase}/chat/stream?${params}`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        setMessages(prev => {
          const newMessages = [...prev];
          const lastMessage = newMessages[newMessages.length - 1];
          
          if (lastMessage.role !== 'assistant') return newMessages;
          
          // Handle different event types from ADK
          if (data.type === 'llm_output') {
            // Only append text for llm_output events
            lastMessage.content += data.text || '';
          } else if (data.type === 'tool_start') {
            if (!lastMessage.tools) lastMessage.tools = [];
            lastMessage.tools.push({
              name: data.name || 'unknown',
              status: 'running',
              args: data.args
            });
          } else if (data.type === 'tool_end') {
            const tool = lastMessage.tools?.find(
              t => t.name === data.name && t.status === 'running'
            );
            if (tool) {
              tool.status = 'complete';
              tool.output = data.output;
              
              // Check if output contains mermaid diagram
              if (typeof data.output === 'object' && data.output?.mermaid) {
                if (!lastMessage.diagrams) lastMessage.diagrams = [];
                lastMessage.diagrams.push(data.output.mermaid);
              }
            }
          } else if (data.type === 'complete') {
            // Stream complete
            setIsStreaming(false);
            eventSource.close();
            eventSourceRef.current = null;
            // Fetch backend status after first repo operation
            if (userMessage.toLowerCase().includes('repo') || 
                userMessage.toLowerCase().includes('load')) {
              fetchBackendStatus();
            }
          } else if (data.type === 'error') {
            lastMessage.content = data.message || 'An error occurred';
            setIsStreaming(false);
            eventSource.close();
            eventSourceRef.current = null;
          }
          
          return newMessages;
        });
      } catch (e) {
        console.error('Failed to parse SSE data:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      setIsStreaming(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMessage = newMessages[newMessages.length - 1];
        if (lastMessage.role === 'assistant' && !lastMessage.content) {
          lastMessage.content = 'Connection error. Please try again.';
        }
        return newMessages;
      });
    };
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-3 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-semibold text-gray-800">ADAM Agent</h1>
            <p className="text-sm text-gray-600">Repository Analysis & Development Assistant</p>
          </div>
          
          {/* Backend Status Widget */}
          {backendStatus && (
            <div className="text-xs bg-gray-50 p-2 rounded border border-gray-200">
              <div className="font-semibold mb-1">Backend Status</div>
              <div>Files: {backendStatus.file_count || 0}</div>
              <div>Backend: {backendStatus.decision_backend || 'none'}</div>
              <div>VVS: {backendStatus.using_vvs ? '✓' : '✗'}</div>
              {backendStatus.chunk_count && (
                <div>Chunks: {backendStatus.chunk_count}</div>
              )}
              <button
                onClick={fetchBackendStatus}
                className="mt-1 text-blue-600 hover:text-blue-800"
              >
                Refresh
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto chat-container">
        <div className="max-w-4xl mx-auto px-4 py-4">
          {messages.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              <p className="mb-2">Welcome! I can help you:</p>
              <ul className="text-sm space-y-1">
                <li>• Analyze repositories and codebases</li>
                <li>• Create Rally work items</li>
                <li>• Generate architecture diagrams</li>
                <li>• Answer questions about your code</li>
              </ul>
              <p className="mt-4 text-sm">Try: "Load repository https://github.com/..."</p>
            </div>
          )}
          
          {messages.map((message, index) => (
            <div key={index} className={`mb-4 ${message.role === 'user' ? 'text-right' : ''}`}>
              <div className={`inline-block max-w-3xl ${message.role === 'user' ? 'ml-auto' : ''}`}>
                {/* Message bubble */}
                <div className={`rounded-lg px-4 py-2 ${
                  message.role === 'user' 
                    ? 'bg-indigo-600 text-white' 
                    : 'bg-white border border-gray-200'
                }`}>
                  <div className="whitespace-pre-wrap">{message.content}</div>
                </div>

                {/* Tools timeline */}
                {message.tools && message.tools.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {message.tools.map((tool, toolIndex) => (
                      <div key={toolIndex} className="flex items-start text-sm text-gray-600">
                        <div className={`w-2 h-2 rounded-full mr-2 mt-1 flex-shrink-0 ${
                          tool.status === 'running' ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'
                        }`} />
                        <div className="flex-1">
                          <span className="font-mono">{tool.name}</span>
                          {tool.args && Object.keys(tool.args).length > 0 && (
                            <span className="ml-2 text-gray-400">
                              ({Object.entries(tool.args).map(([k, v]) => 
                                `${k}: ${JSON.stringify(v)}`).join(', ')})
                            </span>
                          )}
                          {tool.output && (
                            <div className="mt-1 text-gray-500">
                              {typeof tool.output === 'string' 
                                ? tool.output.substring(0, 100) + (tool.output.length > 100 ? '...' : '')
                                : JSON.stringify(tool.output).substring(0, 100) + '...'}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Mermaid diagrams */}
                {message.diagrams && message.diagrams.map((diagram, diagIndex) => (
                  <MermaidDiagram key={diagIndex} chart={diagram} />
                ))}
              </div>
            </div>
          ))}
          
          {isStreaming && (
            <div className="flex items-center text-gray-500 text-sm">
              <div className="animate-pulse">Processing...</div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="bg-white border-t border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-3">
          <div className="flex space-x-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Type your message..."
              disabled={isStreaming}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={isStreaming || !input.trim()}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}