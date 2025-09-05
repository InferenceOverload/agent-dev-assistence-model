import React, { useState, useRef, useEffect } from 'react';
import MermaidDiagram from '@/lib/mermaid';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  tools?: Array<{ name: string; status: 'running' | 'complete'; output?: string }>;
  diagram?: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput('');
    setIsStreaming(true);

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

    // Create assistant message placeholder
    const assistantMessage: Message = { role: 'assistant', content: '', tools: [] };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage }),
      });

      if (!response.ok) throw new Error('Failed to connect');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error('No response body');

      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMessage = newMessages[newMessages.length - 1];
                
                if (data.type === 'llm' && lastMessage.role === 'assistant') {
                  lastMessage.content += data.text;
                } else if (data.type === 'tool_start' && lastMessage.role === 'assistant') {
                  if (!lastMessage.tools) lastMessage.tools = [];
                  lastMessage.tools.push({ name: data.name, status: 'running' });
                } else if (data.type === 'tool_end' && lastMessage.role === 'assistant') {
                  const tool = lastMessage.tools?.find(t => t.name === data.name && t.status === 'running');
                  if (tool) {
                    tool.status = 'complete';
                    tool.output = data.output;
                  }
                } else if (data.type === 'diagram' && lastMessage.role === 'assistant') {
                  lastMessage.diagram = data.mermaid;
                }
                
                return newMessages;
              });
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Stream error:', error);
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMessage = newMessages[newMessages.length - 1];
        if (lastMessage.role === 'assistant') {
          lastMessage.content = 'Sorry, an error occurred while processing your request.';
        }
        return newMessages;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-3">
          <h1 className="text-xl font-semibold text-gray-800">ADAM Agent</h1>
          <p className="text-sm text-gray-600">Repository Analysis & Development Assistant</p>
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
                      <div key={toolIndex} className="flex items-center text-sm text-gray-600">
                        <div className={`w-2 h-2 rounded-full mr-2 ${
                          tool.status === 'running' ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'
                        }`} />
                        <span className="font-mono">{tool.name}</span>
                        {tool.output && (
                          <span className="ml-2 text-gray-500 truncate max-w-xs" title={tool.output}>
                            → {tool.output}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Mermaid diagram */}
                {message.diagram && (
                  <MermaidDiagram chart={message.diagram} />
                )}
              </div>
            </div>
          ))}
          
          {isStreaming && (
            <div className="flex items-center text-gray-500 text-sm">
              <div className="animate-pulse">Thinking...</div>
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