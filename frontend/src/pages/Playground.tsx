import React, { useState, useRef, useEffect } from 'react';
import { api, ChatMessage, ChatCompletionResponse, ApiError } from '@/lib/api';
import { StatusBadge } from '@/components/common/StatusBadge';
import { formatCurrency, formatDuration, formatNumber } from '@/lib/utils';
import { useToast } from '@/components/common/Toast';
import {
  Send,
  Trash2,
  Copy,
  Check,
  Zap,
  Clock,
  Coins,
  Cpu,
  Layers,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Sliders,
} from 'lucide-react';

interface ExtendedMessage extends ChatMessage {
  id: string;
  responseMeta?: ChatCompletionResponse;
  error?: ApiError;
}

const PRESET_PROMPTS = [
  'Explain consistent hashing in distributed systems in two sentences.',
  'Write a Python function to compute the Fibonacci sequence recursively with memoization.',
  'What are the advantages of Redis caching over direct database queries?',
];

export const Playground: React.FC = () => {
  const { success } = useToast();
  const [messages, setMessages] = useState<ExtendedMessage[]>([
    {
      id: 'init-msg',
      role: 'assistant',
      content: 'Hello! I am your LLM Gateway assistant. Send a message to test model routing, caching, and fallback policies.',
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Generation Controls
  const [model, setModel] = useState('cheap');
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [cacheEnabled, setCacheEnabled] = useState(true);
  const [bypassHeader, setBypassHeader] = useState(false);
  const [taskType, setTaskType] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    success('Copied to Clipboard', text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSend = async (textToSend?: string) => {
    const content = (textToSend || input).trim();
    if (!content || isLoading) return;

    const userMsgId = Math.random().toString(36).substring(2, 9);
    const userMessage: ExtendedMessage = {
      id: userMsgId,
      role: 'user',
      content,
    };

    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    // Build payload messages for API
    const apiMessages: ChatMessage[] = newMessages
      .filter((m) => !m.error)
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const response = await api.createChatCompletion(
        {
          model,
          messages: apiMessages,
          temperature,
          max_tokens: maxTokens,
          cache: cacheEnabled,
          task_type: taskType || undefined,
        },
        bypassHeader
      );

      const assistantMsgId = Math.random().toString(36).substring(2, 9);
      const assistantText = response.choices[0]?.message?.content || 'No response generated.';

      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          role: 'assistant',
          content: assistantText,
          responseMeta: response,
        },
      ]);
    } catch (err) {
      const errorMsgId = Math.random().toString(36).substring(2, 9);
      setMessages((prev) => [
        ...prev,
        {
          id: errorMsgId,
          role: 'assistant',
          content: '',
          error: err as ApiError,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([
      {
        id: 'init-msg',
        role: 'assistant',
        content: 'Chat cleared. Ready for your next query.',
      },
    ]);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 animate-in fade-in duration-200">
      {/* Left Chat Column */}
      <div className="lg:col-span-3 flex flex-col h-[calc(100vh-140px)] rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {/* Chat Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-3 bg-card/60 backdrop-blur-xs">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary" />
            <span className="text-sm font-semibold text-foreground">Interactive Session</span>
            <span className="text-xs font-mono bg-muted text-muted-foreground px-2 py-0.5 rounded">
              Model: {model}
            </span>
          </div>

          <button
            onClick={handleClearChat}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground p-1.5 rounded-md hover:bg-muted transition-colors"
            title="Clear message history"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear</span>
          </button>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              {/* Message Bubble */}
              {msg.content && (
                <div
                  className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed shadow-xs ${
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground rounded-br-xs'
                      : 'bg-muted/80 text-foreground border border-border rounded-bl-xs'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              )}

              {/* Error Box */}
              {msg.error && (
                <div className="max-w-[85%] rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-xs text-destructive space-y-2">
                  <div className="flex items-center gap-2 font-semibold">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Error ({msg.error.status || 'Network'}): {msg.error.code}</span>
                  </div>
                  <p className="font-mono text-[11px] bg-background/50 p-2 rounded border border-destructive/20">
                    {msg.error.message}
                  </p>
                  {msg.error.status === 401 && (
                    <p className="text-[11px] text-muted-foreground">
                      Tip: Set your Gateway Key in the topbar button to access authenticated endpoints.
                    </p>
                  )}
                  {msg.error.status === 429 && (
                    <p className="text-[11px] text-muted-foreground">
                      Provider rate limit reached. The gateway attempted exponential retries before failing over.
                    </p>
                  )}
                </div>
              )}

              {/* Rich Metadata Strip on Assistant Messages */}
              {msg.responseMeta && (
                <div className="mt-2 w-full max-w-[85%] rounded-lg border border-border bg-background/60 p-2.5 text-xs text-muted-foreground space-y-2 shadow-xs">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-2">
                    <div className="flex items-center gap-2">
                      <StatusBadge
                        type="cache"
                        value={msg.responseMeta.cached ? 'CACHED' : 'FRESH'}
                      />
                      <span className="font-mono font-medium text-foreground text-[11px] flex items-center gap-1">
                        <Cpu className="w-3 h-3 text-primary" />
                        {msg.responseMeta.provider}
                      </span>
                      <span className="text-border">|</span>
                      <span className="font-mono text-[11px] flex items-center gap-1">
                        <Layers className="w-3 h-3" />
                        {msg.responseMeta.model}
                      </span>
                    </div>

                    <button
                      onClick={() => handleCopy(msg.responseMeta!.request_id, msg.id)}
                      className="inline-flex items-center gap-1 text-[11px] font-mono hover:text-foreground bg-muted/60 px-2 py-0.5 rounded transition-colors"
                      title="Copy Request ID"
                    >
                      {copiedId === msg.id ? (
                        <Check className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                      <span>{msg.responseMeta.request_id.substring(0, 12)}...</span>
                    </button>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
                    <div className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-blue-400" />
                      <span>{formatDuration(msg.responseMeta.latency_ms)}</span>
                    </div>

                    <div className="flex items-center gap-1">
                      <Coins className="w-3 h-3 text-amber-400" />
                      <span>{formatCurrency(msg.responseMeta.cost_usd)}</span>
                    </div>

                    <div className="flex items-center gap-1">
                      <Zap className="w-3 h-3 text-purple-400" />
                      <span>{formatNumber(msg.responseMeta.usage.total_tokens)} tokens</span>
                    </div>

                    <div className="text-right text-[10px] text-muted-foreground truncate" title={msg.responseMeta.routing_reason || ''}>
                      {msg.responseMeta.routing_reason || 'direct'}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground p-3 rounded-lg bg-muted/40 w-fit animate-pulse">
              <RotateCcw className="w-3.5 h-3.5 animate-spin text-primary" />
              <span>Routing request across provider chain...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Preset Quick Prompts */}
        <div className="px-4 py-2 bg-muted/20 border-t border-border flex items-center gap-2 overflow-x-auto text-[11px]">
          <span className="text-muted-foreground shrink-0 font-medium">Try:</span>
          {PRESET_PROMPTS.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(prompt)}
              disabled={isLoading}
              className="shrink-0 rounded border border-border bg-card px-2.5 py-1 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors truncate max-w-xs"
            >
              {prompt}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-3 border-t border-border bg-card flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Type your message to test completions..."
            disabled={isLoading}
            className="flex-1 rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
          />

          <button
            onClick={() => handleSend()}
            disabled={isLoading || !input.trim()}
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 shrink-0"
            aria-label="Send message"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Right Routing & Control Sidebar */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-5 h-fit">
        <div className="flex items-center gap-2 border-b border-border pb-3">
          <Sliders className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">Routing & Generation</h2>
        </div>

        {/* Model Alias / Target */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-foreground flex justify-between">
            <span>Model / Alias</span>
            <span className="font-mono text-[10px] text-muted-foreground">route target</span>
          </label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-2.5 py-2 text-xs font-mono text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <optgroup label="Routing Aliases">
              <option value="cheap">cheap (mock-model)</option>
              <option value="balanced">balanced (gpt-4o-mini)</option>
              <option value="powerful">powerful (gpt-4o)</option>
            </optgroup>
            <optgroup label="Direct Models">
              <option value="mock-model">mock-model (Deterministic)</option>
              <option value="gpt-4o-mini">gpt-4o-mini</option>
              <option value="gpt-4o">gpt-4o</option>
              <option value="claude-3-5-sonnet">claude-3-5-sonnet</option>
            </optgroup>
          </select>
        </div>

        {/* Task Hint Selector */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-foreground flex justify-between">
            <span>Task Type Hint</span>
            <span className="font-mono text-[10px] text-muted-foreground">optional</span>
          </label>
          <select
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            className="w-full rounded-lg border border-border bg-background px-2.5 py-2 text-xs font-mono text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">None (Explicit routing)</option>
            <option value="summarization">summarization &rarr; cheap</option>
            <option value="coding">coding &rarr; powerful</option>
            <option value="chat">chat &rarr; balanced</option>
            <option value="extraction">extraction &rarr; cheap</option>
          </select>
        </div>

        {/* Temperature Slider */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-foreground">Temperature</span>
            <span className="font-mono text-muted-foreground">{temperature.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min="0"
            max="2"
            step="0.05"
            value={temperature}
            onChange={(e) => setTemperature(parseFloat(e.target.value))}
            className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
            <span>0.0 Precise</span>
            <span>2.0 Creative</span>
          </div>
        </div>

        {/* Max Tokens */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-foreground">Max Tokens</span>
            <span className="font-mono text-[10px] text-muted-foreground">1 - 4096</span>
          </div>
          <input
            type="number"
            min="16"
            max="4096"
            value={maxTokens}
            onChange={(e) => setMaxTokens(parseInt(e.target.value) || 256)}
            className="w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-mono text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Caching Toggles */}
        <div className="space-y-3 pt-2 border-t border-border">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-xs font-medium text-foreground">Redis Caching</span>
            <input
              type="checkbox"
              checked={cacheEnabled}
              onChange={(e) => setCacheEnabled(e.target.checked)}
              className="h-4 w-4 rounded border-border text-primary focus:ring-primary accent-primary"
            />
          </label>

          <label className="flex items-center justify-between cursor-pointer">
            <div className="flex flex-col">
              <span className="text-xs font-medium text-foreground">Bypass Cache Header</span>
              <span className="text-[10px] text-muted-foreground">X-Cache-Bypass: true</span>
            </div>
            <input
              type="checkbox"
              checked={bypassHeader}
              onChange={(e) => setBypassHeader(e.target.checked)}
              className="h-4 w-4 rounded border-border text-primary focus:ring-primary accent-primary"
            />
          </label>
        </div>
      </div>
    </div>
  );
};
