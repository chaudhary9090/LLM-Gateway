import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useToast } from '@/components/common/Toast';
import {
  CheckCircle2,
  AlertCircle,
  Database,
  Cpu,
  Server,
  Zap,
  RotateCcw,
  Copy,
  Check,
  Code,
  Gauge,
} from 'lucide-react';

interface ParsedMetric {
  name: string;
  type: string;
  help: string;
  value: string;
  labels?: string;
}

export const HealthMetrics: React.FC = () => {
  const { success } = useToast();
  const [viewRawMetrics, setViewRawMetrics] = useState(false);
  const [copiedRaw, setCopiedRaw] = useState(false);

  // Queries for health, ready, and metrics
  const healthQuery = useQuery({
    queryKey: ['health-info'],
    queryFn: () => api.getHealth(),
    refetchInterval: 10000,
  });

  const readyQuery = useQuery({
    queryKey: ['ready-info'],
    queryFn: () => api.getReady(),
    refetchInterval: 10000,
  });

  const metricsQuery = useQuery({
    queryKey: ['metrics-raw'],
    queryFn: () => api.getMetrics(),
    refetchInterval: 10000,
  });

  // Parse Prometheus text exposition format
  const parsedMetrics = React.useMemo<ParsedMetric[]>(() => {
    if (!metricsQuery.data) return [];

    const lines = metricsQuery.data.split('\n');
    const result: ParsedMetric[] = [];
    const helpMap: Record<string, string> = {};
    const typeMap: Record<string, string> = {};

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      if (trimmed.startsWith('# HELP ')) {
        const parts = trimmed.substring(7).split(' ');
        const metricName = parts[0];
        helpMap[metricName] = parts.slice(1).join(' ');
      } else if (trimmed.startsWith('# TYPE ')) {
        const parts = trimmed.substring(7).split(' ');
        const metricName = parts[0];
        typeMap[metricName] = parts[1];
      } else if (!trimmed.startsWith('#')) {
        // Metric value line: metric_name{labels} value or metric_name value
        const spaceIdx = trimmed.lastIndexOf(' ');
        if (spaceIdx !== -1) {
          const rawName = trimmed.substring(0, spaceIdx);
          const value = trimmed.substring(spaceIdx + 1);

          let name = rawName;
          let labels = '';
          const labelStart = rawName.indexOf('{');
          if (labelStart !== -1) {
            name = rawName.substring(0, labelStart);
            labels = rawName.substring(labelStart);
          }

          result.push({
            name,
            labels,
            value,
            type: typeMap[name] || 'gauge',
            help: helpMap[name] || '',
          });
        }
      }
    }
    return result;
  }, [metricsQuery.data]);

  const handleCopyRaw = () => {
    if (!metricsQuery.data) return;
    navigator.clipboard.writeText(metricsQuery.data);
    setCopiedRaw(true);
    success('Copied', 'Prometheus metrics copied to clipboard.');
    setTimeout(() => setCopiedRaw(false), 2000);
  };


  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            System Health & Prometheus Telemetry
          </h1>
          <p className="text-sm text-muted-foreground">
            Live readiness probes across subsystem dependencies and standardized metrics exposition.
          </p>
        </div>

        <button
          onClick={() => {
            healthQuery.refetch();
            readyQuery.refetch();
            metricsQuery.refetch();
          }}
          disabled={healthQuery.isFetching || readyQuery.isFetching || metricsQuery.isFetching}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors self-start sm:self-auto"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${healthQuery.isFetching ? 'animate-spin text-primary' : ''}`} />
          <span>Refresh All</span>
        </button>
      </div>

      {/* Subsystem Readiness Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Gateway App Status */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs uppercase font-medium">Gateway Service</span>
            <Server className="w-4 h-4 text-primary" />
          </div>
          <div className="flex items-center gap-2">
            {healthQuery.data?.status === 'ok' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-400" />
            )}
            <span className="text-lg font-bold font-mono text-foreground">
              {healthQuery.data?.status === 'ok' ? 'HEALTHY' : 'DEGRADED'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground font-mono">
            Env: {healthQuery.data?.environment || 'development'}
          </p>
        </div>

        {/* Database Readiness */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs uppercase font-medium">SQLite Database</span>
            <Database className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex items-center gap-2">
            {readyQuery.data?.dependencies?.database?.status === 'healthy' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <AlertCircle className="w-5 h-5 text-amber-400" />
            )}
            <span className="text-lg font-bold font-mono text-foreground uppercase">
              {readyQuery.data?.dependencies?.database?.status || 'Probing...'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground truncate" title={readyQuery.data?.dependencies?.database?.message || ''}>
            {readyQuery.data?.dependencies?.database?.message || 'SQLAlchemy engine connected'}
          </p>
        </div>

        {/* Redis Cache Readiness */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs uppercase font-medium">Redis Cache</span>
            <Zap className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="flex items-center gap-2">
            {readyQuery.data?.dependencies?.cache?.status === 'healthy' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <AlertCircle className="w-5 h-5 text-amber-400" />
            )}
            <span className="text-lg font-bold font-mono text-foreground uppercase">
              {readyQuery.data?.dependencies?.cache?.status || 'Probing...'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground truncate" title={readyQuery.data?.dependencies?.cache?.message || ''}>
            {readyQuery.data?.dependencies?.cache?.message || 'Cache backend responsive'}
          </p>
        </div>

        {/* Provider Fleet Readiness */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs uppercase font-medium">Upstream Fleet</span>
            <Cpu className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-center gap-2">
            {readyQuery.data?.dependencies?.providers?.status === 'healthy' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            ) : (
              <AlertCircle className="w-5 h-5 text-amber-400" />
            )}
            <span className="text-lg font-bold font-mono text-foreground uppercase">
              {readyQuery.data?.dependencies?.providers?.status || 'Probing...'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground truncate" title={readyQuery.data?.dependencies?.providers?.message || ''}>
            {readyQuery.data?.dependencies?.providers?.message || 'Providers accessible'}
          </p>
        </div>
      </div>

      {/* Metrics Section */}
      <div className="rounded-xl border border-border bg-card shadow-sm p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-primary" />
            <h2 className="text-base font-semibold text-foreground">Prometheus Metrics (`GET /metrics`)</h2>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewRawMetrics(!viewRawMetrics)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border bg-background hover:bg-muted text-foreground transition-colors"
            >
              <Code className="w-3.5 h-3.5" />
              <span>{viewRawMetrics ? 'Structured View' : 'Raw Text'}</span>
            </button>

            {viewRawMetrics && (
              <button
                onClick={handleCopyRaw}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border bg-background hover:bg-muted text-foreground transition-colors"
                title="Copy raw metrics"
              >
                {copiedRaw ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>Copy</span>
              </button>
            )}
          </div>
        </div>

        {viewRawMetrics ? (
          <div className="rounded-lg border border-border bg-background p-4 overflow-x-auto">
            <pre className="text-xs font-mono text-foreground whitespace-pre-wrap leading-relaxed">
              {metricsQuery.data || 'Loading Prometheus metrics...'}
            </pre>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-muted/50 border-b border-border text-muted-foreground uppercase text-[10px]">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Metric Name</th>
                  <th className="px-4 py-2.5 font-semibold">Type</th>
                  <th className="px-4 py-2.5 font-semibold">Labels / Quantiles</th>
                  <th className="px-4 py-2.5 font-semibold text-right">Value</th>
                  <th className="px-4 py-2.5 font-semibold font-sans">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {metricsQuery.isLoading ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-muted-foreground font-sans animate-pulse">
                      Parsing Prometheus metrics stream...
                    </td>
                  </tr>
                ) : parsedMetrics.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-muted-foreground font-sans">
                      No metrics available.
                    </td>
                  </tr>
                ) : (
                  parsedMetrics.map((m, idx) => (
                    <tr key={idx} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-2.5 font-semibold text-primary">{m.name}</td>
                      <td className="px-4 py-2.5">
                        <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] uppercase text-muted-foreground">
                          {m.type}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground text-[11px]">{m.labels || '—'}</td>
                      <td className="px-4 py-2.5 text-right font-bold text-foreground">{m.value}</td>
                      <td className="px-4 py-2.5 font-sans text-xs text-muted-foreground">{m.help || '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
