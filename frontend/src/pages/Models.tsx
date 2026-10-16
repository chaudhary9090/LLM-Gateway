import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ModelConfigSummary } from '@/lib/api';
import { StatusBadge } from '@/components/common/StatusBadge';
import { formatCurrency } from '@/lib/utils';
import {
  Layers,
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  RotateCcw,
  ArrowRight,
} from 'lucide-react';

type SortField = 'name' | 'tier' | 'primary_provider' | 'input_cost_per_1k' | 'output_cost_per_1k';
type SortOrder = 'asc' | 'desc';

export const Models: React.FC = () => {
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  const { data: models, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['models-list'],
    queryFn: () => api.getModels(),
  });

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const filteredAndSortedModels = useMemo(() => {
    if (!models) return [];

    return models
      .filter((m: ModelConfigSummary) => {
        const query = search.toLowerCase();
        return (
          m.name.toLowerCase().includes(query) ||
          m.tier.toLowerCase().includes(query) ||
          m.capabilities.some((c) => c.toLowerCase().includes(query)) ||
          m.primary_provider.toLowerCase().includes(query)
        );
      })
      .sort((a: ModelConfigSummary, b: ModelConfigSummary) => {
        const aVal = a[sortField];
        const bVal = b[sortField];

        if (typeof aVal === 'string') {
          return sortOrder === 'asc'
            ? aVal.localeCompare(bVal as string)
            : (bVal as string).localeCompare(aVal);
        }
        return sortOrder === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
      });
  }, [models, search, sortField, sortOrder]);

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 text-muted-foreground/50" />;
    }
    return sortOrder === 'asc' ? (
      <ArrowUp className="w-3.5 h-3.5 text-primary" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-primary" />
    );
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Model Catalog & Routing Policy
          </h1>
          <p className="text-sm text-muted-foreground">
            Declarative model registry, primary provider mapping, fallback priority, and token pricing.
          </p>
        </div>

        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors self-start sm:self-auto"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-primary' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Search Input Bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search models, capabilities, tiers, or providers..."
            className="w-full pl-9 pr-4 py-2 text-xs rounded-lg border border-border bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
          />
        </div>
      </div>

      {/* Model Catalog Table */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 border-b border-border text-muted-foreground uppercase tracking-wider text-[10px]">
              <tr>
                <th
                  onClick={() => handleSort('name')}
                  className="px-4 py-3 cursor-pointer hover:text-foreground font-semibold"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Model Name</span>
                    {renderSortIcon('name')}
                  </div>
                </th>
                <th
                  onClick={() => handleSort('tier')}
                  className="px-4 py-3 cursor-pointer hover:text-foreground font-semibold"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Tier</span>
                    {renderSortIcon('tier')}
                  </div>
                </th>
                <th className="px-4 py-3 font-semibold">Capabilities</th>
                <th
                  onClick={() => handleSort('primary_provider')}
                  className="px-4 py-3 cursor-pointer hover:text-foreground font-semibold"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Routing Chain</span>
                    {renderSortIcon('primary_provider')}
                  </div>
                </th>
                <th
                  onClick={() => handleSort('input_cost_per_1k')}
                  className="px-4 py-3 cursor-pointer hover:text-foreground font-semibold text-right"
                >
                  <div className="flex items-center justify-end gap-1.5">
                    <span>Input / 1K</span>
                    {renderSortIcon('input_cost_per_1k')}
                  </div>
                </th>
                <th
                  onClick={() => handleSort('output_cost_per_1k')}
                  className="px-4 py-3 cursor-pointer hover:text-foreground font-semibold text-right"
                >
                  <div className="flex items-center justify-end gap-1.5">
                    <span>Output / 1K</span>
                    {renderSortIcon('output_cost_per_1k')}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-muted-foreground animate-pulse">
                    Loading model catalog...
                  </td>
                </tr>
              ) : isError ? (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-rose-400">
                    Failed to fetch models from backend.
                  </td>
                </tr>
              ) : filteredAndSortedModels.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-muted-foreground">
                    No models match search query "{search}".
                  </td>
                </tr>
              ) : (
                filteredAndSortedModels.map((m: ModelConfigSummary) => (
                  <tr key={m.name} className="hover:bg-muted/30 transition-colors">
                    {/* Model Name */}
                    <td className="px-4 py-3 font-mono font-medium text-foreground">
                      <div className="flex items-center gap-2">
                        <Layers className="w-3.5 h-3.5 text-primary" />
                        <span>{m.name}</span>
                      </div>
                    </td>

                    {/* Tier */}
                    <td className="px-4 py-3">
                      <StatusBadge type="tier" value={m.tier} />
                    </td>

                    {/* Capabilities */}
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {m.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="bg-muted px-1.5 py-0.5 rounded text-[10px] font-mono text-muted-foreground"
                          >
                            {cap}
                          </span>
                        ))}
                      </div>
                    </td>

                    {/* Routing Chain */}
                    <td className="px-4 py-3 font-mono text-xs">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="font-semibold text-foreground px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                          {m.primary_provider}
                        </span>
                        {m.fallback_providers && m.fallback_providers.length > 0 && (
                          <>
                            <ArrowRight className="w-3 h-3 text-muted-foreground" />
                            {m.fallback_providers.map((fb, idx) => (
                              <React.Fragment key={fb}>
                                <span className="text-muted-foreground px-1 py-0.5 rounded bg-muted">
                                  {fb}
                                </span>
                                {idx < m.fallback_providers.length - 1 && (
                                  <ArrowRight className="w-2.5 h-2.5 text-muted-foreground/60" />
                                )}
                              </React.Fragment>
                            ))}
                          </>
                        )}
                      </div>
                    </td>

                    {/* Input Price */}
                    <td className="px-4 py-3 font-mono text-right text-muted-foreground">
                      {formatCurrency(m.input_cost_per_1k)}
                    </td>

                    {/* Output Price */}
                    <td className="px-4 py-3 font-mono text-right text-muted-foreground">
                      {formatCurrency(m.output_cost_per_1k)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
