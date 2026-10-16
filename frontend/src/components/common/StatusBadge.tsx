import React from 'react';
import { cn } from '@/lib/utils';
import { ShieldCheck, ShieldAlert, ShieldX, CheckCircle, AlertCircle, Zap, Database } from 'lucide-react';

interface StatusBadgeProps {
  type: 'circuit' | 'health' | 'cache' | 'status' | 'tier';
  value: string;
  className?: string;
  showIcon?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  type,
  value,
  className,
  showIcon = true,
}) => {
  const val = value.toUpperCase();

  if (type === 'circuit') {
    if (val === 'CLOSED') {
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20',
            className
          )}
        >
          {showIcon && <ShieldCheck className="w-3.5 h-3.5" />}
          CLOSED
        </span>
      );
    }
    if (val === 'HALF_OPEN') {
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/20 animate-pulse',
            className
          )}
        >
          {showIcon && <ShieldAlert className="w-3.5 h-3.5" />}
          HALF_OPEN
        </span>
      );
    }
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-500 border border-rose-500/20',
          className
        )}
      >
        {showIcon && <ShieldX className="w-3.5 h-3.5" />}
        OPEN
      </span>
    );
  }

  if (type === 'cache') {
    const isHit = value.toLowerCase() === 'true' || val === 'HIT' || val === 'CACHED';
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border font-mono',
          isHit
            ? 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30'
            : 'bg-muted text-muted-foreground border-border',
          className
        )}
      >
        {showIcon && (isHit ? <Zap className="w-3 h-3 text-cyan-400" /> : <Database className="w-3 h-3" />)}
        {isHit ? 'CACHED' : 'FRESH'}
      </span>
    );
  }

  if (type === 'status') {
    const isSuccess = val === 'SUCCESS' || val === 'OK' || val === '200';
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
          isSuccess
            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
          className
        )}
      >
        {showIcon && (isSuccess ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />)}
        {value}
      </span>
    );
  }

  if (type === 'tier') {
    const colorMap: Record<string, string> = {
      CHEAP: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      BALANCED: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      POWERFUL: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    };
    return (
      <span
        className={cn(
          'inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider border',
          colorMap[val] || 'bg-muted text-muted-foreground border-border',
          className
        )}
      >
        {value}
      </span>
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted text-foreground border border-border',
        className
      )}
    >
      {value}
    </span>
  );
};
