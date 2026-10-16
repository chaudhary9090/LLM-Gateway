import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { MetricCard } from '@/components/common/MetricCard';
import { formatCurrency, formatNumber, formatDuration } from '@/lib/utils';
import {
  Activity,
  Zap,
  ShieldAlert,
  Clock,
  Layers,
  DollarSign,
  CheckCircle,
  Pause,
  Play,
  RotateCcw,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  PieChart,
  Pie,
  Legend,
} from 'recharts';

export const Overview: React.FC = () => {
  const [isPolling, setIsPolling] = useState(true);

  const { data: stats, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['gateway-stats'],
    queryFn: () => api.getStats(),
    refetchInterval: isPolling ? 5000 : false,
  });

  const successRate = stats && stats.total_requests > 0
    ? ((stats.successful_requests / stats.total_requests) * 100).toFixed(1)
    : '100.0';

  const cacheRate = stats && stats.total_requests > 0
    ? (stats.cache_hit_rate * 100).toFixed(1)
    : '0.0';

  // Chart data: Latency percentiles
  const latencyData = stats ? [
    { name: 'p50', value: stats.latency_p50_ms, fill: '#3b82f6' },
    { name: 'p95', value: stats.latency_p95_ms, fill: '#8b5cf6' },
    { name: 'p99', value: stats.latency_p99_ms, fill: '#ec4899' },
  ] : [];

  // Chart data: Cache hit vs miss
  const cacheData = stats ? [
    { name: 'Cache Hits', value: stats.cache_hits, color: '#06b6d4' },
    { name: 'Cache Misses', value: stats.cache_misses, color: '#64748b' },
  ] : [];

  // Chart data: Request outcomes
  const outcomeData = stats ? [
    { name: 'Success', value: stats.successful_requests, color: '#10b981' },
    { name: 'Failures', value: stats.failed_requests, color: '#f43f5e' },
  ] : [];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Gateway Telemetry Overview
          </h1>
          <p className="text-sm text-muted-foreground">
            Real-time operational statistics, latency percentiles, and cost accounting.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={() => setIsPolling(!isPolling)}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
              isPolling
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                : 'border-border bg-card text-muted-foreground hover:text-foreground'
            }`}
          >
            {isPolling ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {isPolling ? 'Auto-refresh: 5s' : 'Polling Paused'}
          </button>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            title="Refresh statistics now"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-primary' : ''}`} />
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Requests"
          value={formatNumber(stats?.total_requests)}
          subtext={`${formatNumber(stats?.successful_requests)} successful`}
          icon={Activity}
          loading={isLoading}
        />

        <MetricCard
          title="Success Rate"
          value={`${successRate}%`}
          subtext={`${formatNumber(stats?.failed_requests)} errors recorded`}
          icon={CheckCircle}
          loading={isLoading}
        />

        <MetricCard
          title="Cache Hit Rate"
          value={`${cacheRate}%`}
          subtext={`${formatNumber(stats?.cache_hits)} hits / ${formatNumber(stats?.cache_misses)} misses`}
          icon={Zap}
          loading={isLoading}
        />

        <MetricCard
          title="Fallback Count"
          value={formatNumber(stats?.fallback_count)}
          subtext="Automatic provider failovers"
          icon={ShieldAlert}
          loading={isLoading}
        />

        <MetricCard
          title="p50 Latency (Median)"
          value={formatDuration(stats?.latency_p50_ms)}
          subtext={`p95: ${formatDuration(stats?.latency_p95_ms)} | p99: ${formatDuration(stats?.latency_p99_ms)}`}
          icon={Clock}
          loading={isLoading}
        />

        <MetricCard
          title="Total Tokens"
          value={formatNumber(stats?.total_tokens)}
          subtext={`${formatNumber(stats?.total_input_tokens)} in / ${formatNumber(stats?.total_output_tokens)} out`}
          icon={Layers}
          loading={isLoading}
        />

        <MetricCard
          title="Estimated Cost"
          value={formatCurrency(stats?.total_estimated_cost_usd)}
          subtext="Estimated model token pricing"
          icon={DollarSign}
          loading={isLoading}
        />

        <MetricCard
          title="Tail Latency (p99)"
          value={formatDuration(stats?.latency_p99_ms)}
          subtext="99th percentile worst-case latency"
          icon={Clock}
          loading={isLoading}
        />
      </div>

      {/* Visual Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Latency Percentiles Bar Chart */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Latency Percentiles (ms)</h2>
              <p className="text-xs text-muted-foreground">End-to-end response time</p>
            </div>
            <div className="text-xs font-mono text-muted-foreground bg-muted px-2 py-0.5 rounded">
              lower is better
            </div>
          </div>

          <div className="h-64 w-full">
            {stats && stats.total_requests > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={latencyData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <XAxis dataKey="name" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `${val}ms`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    formatter={(value: any) => [`${Number(value).toFixed(2)} ms`, 'Latency']}
                  />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {latencyData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                No request traffic recorded yet.
              </div>
            )}
          </div>
        </div>

        {/* Cache Hit vs Miss Pie Chart */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Cache Ratio</h2>
              <p className="text-xs text-muted-foreground">Redis SHA-256 hits vs misses</p>
            </div>
            <span className="text-xs font-mono text-cyan-400 font-semibold">{cacheRate}% Hit</span>
          </div>

          <div className="h-64 w-full">
            {stats && (stats.cache_hits > 0 || stats.cache_misses > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={cacheData}
                    cx="50%"
                    cy="45%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {cacheData.map((entry, index) => (
                      <Cell key={`pie-cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                  />
                  <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                No cached requests recorded yet.
              </div>
            )}
          </div>
        </div>

        {/* Success vs Failed Pie Chart */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Request Outcomes</h2>
              <p className="text-xs text-muted-foreground">Successful vs failed completions</p>
            </div>
            <span className="text-xs font-mono text-emerald-400 font-semibold">{successRate}% OK</span>
          </div>

          <div className="h-64 w-full">
            {stats && (stats.successful_requests > 0 || stats.failed_requests > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={outcomeData}
                    cx="50%"
                    cy="45%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {outcomeData.map((entry, index) => (
                      <Cell key={`outcome-cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                  />
                  <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                No requests recorded yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
