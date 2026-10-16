import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, RequestLogItem } from '@/lib/api';
import { StatusBadge } from '@/components/common/StatusBadge';
import { formatDate, formatDuration, formatCurrency, formatNumber, exportToCSV } from '@/lib/utils';
import { useToast } from '@/components/common/Toast';
import {
  FileText,
  Download,
  Search,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Copy,
  Check,
  X,
  Clock,
  Coins,
  AlertTriangle,
} from 'lucide-react';

export const Logs: React.FC = () => {
  const { success } = useToast();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selectedLog, setSelectedLog] = useState<RequestLogItem | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const { data: logsData, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['request-logs', page, pageSize, statusFilter],
    queryFn: () =>
      api.getLogs({
        page,
        pageSize,
        status: statusFilter,
      }),
    refetchInterval: 10000,
  });

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    success('Copied', text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleExportCSV = () => {
    if (!logsData?.items?.length) return;
    exportToCSV(`llm_gateway_logs_page_${page}.csv`, logsData.items as unknown as Record<string, unknown>[]);
    success('Export Complete', `Saved ${logsData.items.length} records to CSV.`);
  };

  const totalPages = logsData ? Math.max(1, Math.ceil(logsData.total / pageSize)) : 1;

  // Filter items in current page by search query
  const filteredItems = (logsData?.items || []).filter((item) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      item.request_id.toLowerCase().includes(q) ||
      item.model.toLowerCase().includes(q) ||
      item.provider.toLowerCase().includes(q) ||
      (item.routing_reason && item.routing_reason.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Server Audit & Request Logs
          </h1>
          <p className="text-sm text-muted-foreground">
            Persistent execution telemetry, token consumption, and routing decisions.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={handleExportCSV}
            disabled={!logsData?.items?.length}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            title="Export current page to CSV"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>

          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <RotateCcw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-primary' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search request ID, model, provider, or routing reason..."
            className="w-full pl-9 pr-4 py-2 text-xs rounded-lg border border-border bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
          />
        </div>

        <div className="flex items-center gap-2">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="all">All Outcomes</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
          </select>

          {/* Page Size */}
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(parseInt(e.target.value));
              setPage(1);
            }}
            className="rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="10">10 / page</option>
            <option value="20">20 / page</option>
            <option value="50">50 / page</option>
          </select>
        </div>
      </div>

      {/* Logs Table */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 border-b border-border text-muted-foreground uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-4 py-3 font-semibold">Request ID</th>
                <th className="px-4 py-3 font-semibold">Timestamp</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Cache</th>
                <th className="px-4 py-3 font-semibold">Model & Provider</th>
                <th className="px-4 py-3 font-semibold text-right">Latency</th>
                <th className="px-4 py-3 font-semibold text-right">Tokens</th>
                <th className="px-4 py-3 font-semibold text-right">Est. Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-muted-foreground animate-pulse">
                    Loading request audit logs...
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-rose-400">
                    Failed to fetch logs from database.
                  </td>
                </tr>
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-muted-foreground">
                    No log records found matching your filters.
                  </td>
                </tr>
              ) : (
                filteredItems.map((log) => (
                  <tr
                    key={log.request_id}
                    onClick={() => setSelectedLog(log)}
                    className="hover:bg-muted/40 cursor-pointer transition-colors"
                  >
                    {/* Request ID */}
                    <td className="px-4 py-3 font-mono text-[11px] font-medium text-foreground">
                      <div className="flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-primary shrink-0" />
                        <span className="truncate max-w-[110px]">{log.request_id}</span>
                      </div>
                    </td>

                    {/* Timestamp */}
                    <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                      {formatDate(log.timestamp)}
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge type="status" value={log.status} />
                    </td>

                    {/* Cache */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <StatusBadge type="cache" value={log.cache_hit ? 'CACHED' : 'FRESH'} />
                    </td>

                    {/* Model & Provider */}
                    <td className="px-4 py-3 font-mono text-[11px] whitespace-nowrap">
                      <span className="text-foreground font-semibold">{log.model}</span>
                      <span className="text-muted-foreground ml-1.5 text-[10px]">({log.provider})</span>
                    </td>

                    {/* Latency */}
                    <td className="px-4 py-3 font-mono text-right text-muted-foreground whitespace-nowrap">
                      {formatDuration(log.latency_ms)}
                    </td>

                    {/* Tokens */}
                    <td className="px-4 py-3 font-mono text-right text-muted-foreground whitespace-nowrap">
                      {formatNumber(log.total_tokens)}
                    </td>

                    {/* Cost */}
                    <td className="px-4 py-3 font-mono text-right text-muted-foreground whitespace-nowrap">
                      {formatCurrency(log.estimated_cost_usd)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Server Pagination Footer */}
        <div className="flex items-center justify-between border-t border-border px-4 py-3 bg-muted/20 text-xs text-muted-foreground">
          <div>
            Showing <span className="font-semibold text-foreground">{filteredItems.length}</span> of{' '}
            <span className="font-semibold text-foreground">{logsData?.total || 0}</span> total logs
          </div>

          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">
              Page {page} of {totalPages}
            </span>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || isLoading}
                className="flex h-7 w-7 items-center justify-center rounded border border-border text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                aria-label="Previous page"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || isLoading}
                className="flex h-7 w-7 items-center justify-center rounded border border-border text-foreground hover:bg-muted disabled:opacity-40 transition-colors"
                aria-label="Next page"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Row-Detail Slide-Over Drawer */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-lg bg-card border-l border-border h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-primary" />
                <h3 className="text-base font-semibold text-foreground">Request Details</h3>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Drawer Content */}
            <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs font-mono">
              {/* Request ID Strip */}
              <div className="bg-muted/50 p-3 rounded-lg border border-border space-y-1">
                <span className="text-[10px] uppercase text-muted-foreground block">Request ID</span>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-foreground font-semibold text-xs select-all">
                    {selectedLog.request_id}
                  </span>
                  <button
                    onClick={() => handleCopy(selectedLog.request_id, 'drawer-id')}
                    className="p-1 text-muted-foreground hover:text-foreground"
                    title="Copy ID"
                  >
                    {copiedId === 'drawer-id' ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </div>

              {/* Status and Latency Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="border border-border rounded-lg p-3 space-y-1">
                  <span className="text-[10px] uppercase text-muted-foreground">Execution Status</span>
                  <div>
                    <StatusBadge type="status" value={selectedLog.status} />
                  </div>
                </div>

                <div className="border border-border rounded-lg p-3 space-y-1">
                  <span className="text-[10px] uppercase text-muted-foreground">Cache Status</span>
                  <div>
                    <StatusBadge type="cache" value={selectedLog.cache_hit ? 'CACHED' : 'FRESH'} />
                  </div>
                </div>

                <div className="border border-border rounded-lg p-3 space-y-1">
                  <span className="text-[10px] uppercase text-muted-foreground">Latency</span>
                  <p className="text-foreground font-bold text-sm flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-blue-400" />
                    {formatDuration(selectedLog.latency_ms)}
                  </p>
                </div>

                <div className="border border-border rounded-lg p-3 space-y-1">
                  <span className="text-[10px] uppercase text-muted-foreground">Estimated Cost</span>
                  <p className="text-foreground font-bold text-sm flex items-center gap-1">
                    <Coins className="w-3.5 h-3.5 text-amber-400" />
                    {formatCurrency(selectedLog.estimated_cost_usd)}
                  </p>
                </div>
              </div>

              {/* Routing and Resilience */}
              <div className="border border-border rounded-lg p-3 space-y-2">
                <span className="text-[10px] uppercase text-muted-foreground font-sans font-semibold">
                  Routing & Resilience Metadata
                </span>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-muted-foreground block">Target Model:</span>
                    <span className="text-foreground font-semibold">{selectedLog.model}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Selected Provider:</span>
                    <span className="text-foreground font-semibold">{selectedLog.provider}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Attempt Count:</span>
                    <span className="text-foreground">{selectedLog.attempt_count}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Fallback Events:</span>
                    <span className="text-foreground">{selectedLog.fallback_count}</span>
                  </div>
                </div>

                {selectedLog.routing_reason && (
                  <div className="pt-2 border-t border-border">
                    <span className="text-muted-foreground text-[10px] block">Routing Reason:</span>
                    <span className="text-foreground text-[11px] bg-background p-1.5 rounded block mt-0.5 border border-border">
                      {selectedLog.routing_reason}
                    </span>
                  </div>
                )}
              </div>

              {/* Token Breakdown */}
              <div className="border border-border rounded-lg p-3 space-y-2">
                <span className="text-[10px] uppercase text-muted-foreground font-sans font-semibold">
                  Token Accounting
                </span>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-muted/40 p-2 rounded">
                    <span className="text-[10px] text-muted-foreground block">Prompt</span>
                    <span className="font-bold text-foreground">{formatNumber(selectedLog.input_tokens)}</span>
                  </div>
                  <div className="bg-muted/40 p-2 rounded">
                    <span className="text-[10px] text-muted-foreground block">Completion</span>
                    <span className="font-bold text-foreground">{formatNumber(selectedLog.output_tokens)}</span>
                  </div>
                  <div className="bg-primary/10 p-2 rounded border border-primary/20">
                    <span className="text-[10px] text-primary block">Total</span>
                    <span className="font-bold text-primary">{formatNumber(selectedLog.total_tokens)}</span>
                  </div>
                </div>
              </div>

              {/* Error Message if Failed */}
              {selectedLog.error_message && (
                <div className="border border-destructive/30 bg-destructive/10 rounded-lg p-3 space-y-1">
                  <div className="flex items-center gap-1.5 text-destructive font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Error Message</span>
                  </div>
                  <p className="text-[11px] text-destructive/90 break-words whitespace-pre-wrap bg-background/40 p-2 rounded border border-destructive/20">
                    {selectedLog.error_message}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
