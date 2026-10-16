import { z } from 'zod';

// ==========================================
// ZOD SCHEMAS FOR BACKEND API
// ==========================================

export const ChatMessageSchema = z.object({
  role: z.enum(['system', 'user', 'assistant']),
  content: z.string(),
});
export type ChatMessage = z.infer<typeof ChatMessageSchema>;

export const UsageInfoSchema = z.object({
  prompt_tokens: z.number().default(0),
  completion_tokens: z.number().default(0),
  total_tokens: z.number().default(0),
  is_estimated: z.boolean().default(false),
});
export type UsageInfo = z.infer<typeof UsageInfoSchema>;

export const ChatChoiceSchema = z.object({
  index: z.number().default(0),
  message: z.object({
    role: z.string().default('assistant'),
    content: z.string().default(''),
  }),
  finish_reason: z.string().default('stop'),
});
export type ChatChoice = z.infer<typeof ChatChoiceSchema>;

export const ChatCompletionResponseSchema = z.object({
  id: z.string(),
  request_id: z.string(),
  object: z.string().default('chat.completion'),
  created: z.number(),
  model: z.string(),
  provider: z.string(),
  choices: z.array(ChatChoiceSchema),
  usage: UsageInfoSchema,
  cached: z.boolean().default(false),
  latency_ms: z.number().default(0),
  cost_usd: z.number().nullable().optional(),
  routing_reason: z.string().nullable().optional(),
});
export type ChatCompletionResponse = z.infer<typeof ChatCompletionResponseSchema>;

export const GatewayStatsResponseSchema = z.object({
  total_requests: z.number().default(0),
  successful_requests: z.number().default(0),
  failed_requests: z.number().default(0),
  cache_hits: z.number().default(0),
  cache_misses: z.number().default(0),
  cache_hit_rate: z.number().default(0),
  fallback_count: z.number().default(0),
  latency_p50_ms: z.number().default(0),
  latency_p95_ms: z.number().default(0),
  latency_p99_ms: z.number().default(0),
  total_input_tokens: z.number().default(0),
  total_output_tokens: z.number().default(0),
  total_tokens: z.number().default(0),
  total_estimated_cost_usd: z.number().default(0),
});
export type GatewayStatsResponse = z.infer<typeof GatewayStatsResponseSchema>;

export const ProviderSummarySchema = z.object({
  name: z.string(),
  type: z.string(),
  enabled: z.boolean(),
  healthy: z.boolean(),
  circuit_state: z.enum(['CLOSED', 'OPEN', 'HALF_OPEN']),
  failure_count: z.number().default(0),
});
export type ProviderSummary = z.infer<typeof ProviderSummarySchema>;

export const ModelConfigSummarySchema = z.object({
  name: z.string(),
  tier: z.string(),
  capabilities: z.array(z.string()).default([]),
  primary_provider: z.string(),
  fallback_providers: z.array(z.string()).default([]),
  input_cost_per_1k: z.number().default(0),
  output_cost_per_1k: z.number().default(0),
});
export type ModelConfigSummary = z.infer<typeof ModelConfigSummarySchema>;

export const RequestLogItemSchema = z.object({
  request_id: z.string(),
  timestamp: z.string(),
  model: z.string(),
  provider: z.string(),
  status: z.string(),
  cache_hit: z.boolean(),
  attempt_count: z.number(),
  fallback_count: z.number(),
  latency_ms: z.number(),
  input_tokens: z.number(),
  output_tokens: z.number(),
  total_tokens: z.number(),
  estimated_cost_usd: z.number(),
  routing_reason: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
});
export type RequestLogItem = z.infer<typeof RequestLogItemSchema>;

export const PaginatedLogsResponseSchema = z.object({
  items: z.array(RequestLogItemSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});
export type PaginatedLogsResponse = z.infer<typeof PaginatedLogsResponseSchema>;

export const HealthResponseSchema = z.object({
  status: z.string(),
  app: z.string(),
  environment: z.string(),
  timestamp: z.number(),
});
export type HealthResponse = z.infer<typeof HealthResponseSchema>;

export const DependencyStatusSchema = z.object({
  status: z.string(),
  message: z.string().nullable().optional(),
});

export const ReadyResponseSchema = z.object({
  status: z.string(),
  dependencies: z.record(DependencyStatusSchema),
});
export type ReadyResponse = z.infer<typeof ReadyResponseSchema>;

export interface ChatCompletionRequestPayload {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
  timeout?: number;
  cache?: boolean;
  task_type?: string;
  metadata?: Record<string, unknown>;
}

export interface ApiError {
  status: number;
  code: string;
  message: string;
  requestId?: string;
  isRetryable?: boolean;
}

// ==========================================
// API CLIENT IMPLEMENTATION
// ==========================================

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
const API_KEY_STORAGE_KEY = 'llm_gateway_api_key';

export function getGatewayApiKey(): string {
  return sessionStorage.getItem(API_KEY_STORAGE_KEY) || import.meta.env.VITE_GATEWAY_API_KEY || '';
}

export function setGatewayApiKey(key: string): void {
  if (key) {
    sessionStorage.setItem(API_KEY_STORAGE_KEY, key.trim());
  } else {
    sessionStorage.removeItem(API_KEY_STORAGE_KEY);
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  schema?: z.ZodType<T, any, any>
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  headers.set('Accept', 'application/json');
  if (!headers.has('Content-Type') && options.method && options.method !== 'GET') {
    headers.set('Content-Type', 'application/json');
  }

  const apiKey = getGatewayApiKey();
  if (apiKey) {
    headers.set('Authorization', `Bearer ${apiKey}`);
    headers.set('X-API-Key', apiKey);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 35000); // 35s timeout

  try {
    const res = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorBody: Record<string, unknown> = {};
      try {
        errorBody = await res.json();
      } catch {
        errorBody = { message: await res.text() };
      }

      const errDetail = (errorBody.error as Record<string, unknown>) || errorBody;
      const apiErr: ApiError = {
        status: res.status,
        code: (errDetail.code as string) || `http_${res.status}`,
        message: (errDetail.message as string) || (errorBody.detail as string) || res.statusText || 'Unknown error',
        requestId: (errDetail.request_id as string) || res.headers.get('X-Request-ID') || undefined,
        isRetryable: Boolean(errDetail.is_retryable),
      };
      throw apiErr;
    }

    if (endpoint === '/metrics') {
      return (await res.text()) as unknown as T;
    }

    const json = await res.json();
    if (schema) {
      return schema.parse(json);
    }
    return json as T;
  } catch (err) {
    clearTimeout(timeoutId);
    if ((err as Error).name === 'AbortError') {
      throw {
        status: 504,
        code: 'request_timeout',
        message: 'Request to gateway timed out after 35 seconds.',
      } as ApiError;
    }
    if ((err as ApiError).status) {
      throw err;
    }
    throw {
      status: 0,
      code: 'network_error',
      message: (err as Error).message || 'Failed to connect to LLM Gateway.',
    } as ApiError;
  }
}

// ==========================================
// EXPORTED API METHODS
// ==========================================

export const api = {
  getHealth: () => request<HealthResponse>('/health', { method: 'GET' }, HealthResponseSchema),
  getReady: () => request<ReadyResponse>('/ready', { method: 'GET' }, ReadyResponseSchema),
  getStats: () => request<GatewayStatsResponse>('/stats', { method: 'GET' }, GatewayStatsResponseSchema),
  getProviders: () => request<ProviderSummary[]>('/providers', { method: 'GET' }, z.array(ProviderSummarySchema)),
  getModels: () => request<ModelConfigSummary[]>('/models', { method: 'GET' }, z.array(ModelConfigSummarySchema)),
  getLogs: (params: {
    page?: number;
    pageSize?: number;
    provider?: string;
    model?: string;
    status?: string;
  } = {}) => {
    const q = new URLSearchParams();
    if (params.page) q.set('page', params.page.toString());
    if (params.pageSize) q.set('page_size', params.pageSize.toString());
    if (params.provider) q.set('provider', params.provider);
    if (params.model) q.set('model', params.model);
    if (params.status && params.status !== 'all') q.set('status', params.status);

    const queryStr = q.toString() ? `?${q.toString()}` : '';
    return request<PaginatedLogsResponse>(`/logs${queryStr}`, { method: 'GET' }, PaginatedLogsResponseSchema);
  },
  getMetrics: () => request<string>('/metrics', { method: 'GET' }),
  createChatCompletion: (
    payload: ChatCompletionRequestPayload,
    bypassCacheHeader: boolean = false
  ) => {
    const headers: Record<string, string> = {};
    if (bypassCacheHeader) {
      headers['X-Cache-Bypass'] = 'true';
    }
    return request<ChatCompletionResponse>(
      '/v1/chat/completions',
      {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      },
      ChatCompletionResponseSchema
    );
  },
};
