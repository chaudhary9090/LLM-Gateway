import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ProviderSummary } from '@/lib/api';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Cpu, RotateCcw, AlertTriangle, HeartPulse } from 'lucide-react';

export const Providers: React.FC = () => {
  const { data: providers, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['providers-list'],
    queryFn: () => api.getProviders(),
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Provider Architecture & Circuit Breakers
          </h1>
          <p className="text-sm text-muted-foreground">
            Monitor real-time upstream provider status, health probes, and per-adapter circuit breaker states.
          </p>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors self-start sm:self-auto"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-primary' : ''}`} />
          <span>Refresh Providers</span>
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-44 rounded-xl border border-border bg-card p-5 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="p-6 rounded-xl border border-destructive/30 bg-destructive/5 text-center text-destructive">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
          <p className="text-sm font-semibold">Failed to fetch provider status.</p>
          <p className="text-xs text-muted-foreground mt-1">Ensure the backend is running at http://localhost:8000.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {providers?.map((provider: ProviderSummary) => (
            <div
              key={provider.name}
              className={`rounded-xl border bg-card p-5 shadow-sm transition-all hover:border-border/80 ${
                provider.enabled
                  ? 'border-border'
                  : 'border-border/40 opacity-70 bg-muted/20'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-lg ${provider.enabled ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}`}>
                    <Cpu className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-foreground font-mono">
                      {provider.name}
                    </h3>
                    <span className="text-xs text-muted-foreground font-mono">
                      Type: {provider.type}
                    </span>
                  </div>
                </div>

                <StatusBadge type="circuit" value={provider.circuit_state} />
              </div>

              <div className="mt-5 grid grid-cols-3 gap-3 border-t border-border/60 pt-4 text-xs font-mono">
                <div>
                  <span className="text-muted-foreground text-[10px] uppercase tracking-wider block mb-1">
                    Enabled
                  </span>
                  <span className={`font-semibold ${provider.enabled ? 'text-emerald-400' : 'text-muted-foreground'}`}>
                    {provider.enabled ? 'Active' : 'Disabled'}
                  </span>
                </div>

                <div>
                  <span className="text-muted-foreground text-[10px] uppercase tracking-wider block mb-1">
                    Health Probe
                  </span>
                  <span className={`font-semibold flex items-center gap-1 ${provider.healthy ? 'text-emerald-400' : 'text-rose-400'}`}>
                    <HeartPulse className="w-3.5 h-3.5" />
                    {provider.healthy ? 'Passing' : 'Failing'}
                  </span>
                </div>

                <div>
                  <span className="text-muted-foreground text-[10px] uppercase tracking-wider block mb-1">
                    Failures
                  </span>
                  <span className={`font-semibold ${provider.failure_count > 0 ? 'text-rose-400' : 'text-muted-foreground'}`}>
                    {provider.failure_count} consecutive
                  </span>
                </div>
              </div>

              {/* Explanatory notes */}
              <div className="mt-3 bg-muted/40 rounded-lg p-2.5 text-[11px] text-muted-foreground flex items-center justify-between">
                <span>
                  {provider.circuit_state === 'CLOSED' && 'Operating normally. All requests pass through.'}
                  {provider.circuit_state === 'HALF_OPEN' && 'Probing recovery with test traffic.'}
                  {provider.circuit_state === 'OPEN' && 'Circuit tripped open. Requests fail over immediately.'}
                </span>
                <span className="text-[10px] font-mono text-border font-semibold">
                  Threshold: 5
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
