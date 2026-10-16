import React from 'react';
import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtext?: string;
  icon: LucideIcon;
  badge?: React.ReactNode;
  loading?: boolean;
  className?: string;
  trend?: 'up' | 'down' | 'neutral';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtext,
  icon: Icon,
  badge,
  loading = false,
  className,
}) => {
  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-sm transition-all hover:border-border/80 hover:shadow-md',
        className
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </span>
        <div className="flex items-center gap-2">
          {badge}
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <Icon className="h-4 w-4" />
          </div>
        </div>
      </div>

      <div className="mt-3">
        {loading ? (
          <div className="h-8 w-24 animate-pulse rounded bg-muted"></div>
        ) : (
          <div className="text-2xl font-bold tracking-tight text-foreground font-mono">
            {value}
          </div>
        )}

        {subtext && (
          <p className="mt-1 text-xs text-muted-foreground">
            {subtext}
          </p>
        )}
      </div>
    </div>
  );
};
