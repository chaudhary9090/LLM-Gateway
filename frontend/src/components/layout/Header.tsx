import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, getGatewayApiKey, setGatewayApiKey } from '@/lib/api';
import { useTheme } from '@/lib/theme';
import { useToast } from '@/components/common/Toast';
import {
  Sun,
  Moon,
  Key,
  Menu,
  Check,
  X,
  Server,
} from 'lucide-react';

interface HeaderProps {
  onToggleSidebar?: () => void;
  collapsed?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const { theme, toggleTheme } = useTheme();
  const { success } = useToast();
  const [isKeyModalOpen, setIsKeyModalOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState(getGatewayApiKey());

  // Poll gateway health every 10s for status pulse
  const { data: healthData, isError, isLoading } = useQuery({
    queryKey: ['health-status'],
    queryFn: () => api.getHealth(),
    refetchInterval: 10000,
  });

  const handleSaveApiKey = (e: React.FormEvent) => {
    e.preventDefault();
    setGatewayApiKey(apiKeyInput);
    setIsKeyModalOpen(false);
    success('Gateway Key Saved', apiKeyInput ? 'Authentication header attached to all requests.' : 'Gateway key removed.');
  };

  const isLive = !isError && !isLoading && healthData?.status === 'ok';

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            onClick={onToggleSidebar}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-accent hover:text-foreground md:hidden"
            aria-label="Toggle menu"
          >
            <Menu className="h-4 w-4" />
          </button>

          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 relative">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  isLive ? 'bg-emerald-400' : 'bg-rose-400'
                }`}
              ></span>
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  isLive ? 'bg-emerald-500' : 'bg-rose-500'
                }`}
              ></span>
            </span>
            <span className="text-xs font-mono font-medium text-muted-foreground flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5" />
              {isLive ? 'Gateway Online' : 'Gateway Disconnected'}
            </span>
            {healthData?.environment && (
              <span className="text-[10px] font-mono uppercase bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                {healthData.environment}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick API Key Button */}
          <button
            onClick={() => {
              setApiKeyInput(getGatewayApiKey());
              setIsKeyModalOpen(true);
            }}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors ${
              getGatewayApiKey()
                ? 'border-primary/40 bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:bg-accent hover:text-foreground'
            }`}
            title="Configure Gateway API Key"
          >
            <Key className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">
              {getGatewayApiKey() ? 'API Key Set' : 'Auth Key'}
            </span>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </header>

      {/* API Key Modal */}
      {isKeyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Key className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-foreground">Gateway Authentication</h3>
                  <p className="text-xs text-muted-foreground">Inbound API key for protected routes</p>
                </div>
              </div>
              <button
                onClick={() => setIsKeyModalOpen(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveApiKey} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-foreground mb-1.5">
                  Client Gateway Key
                </label>
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder="Leave empty if auth is disabled in .env"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  Stored securely in browser <code className="text-xs font-mono">sessionStorage</code>. Never stored or logged on disks.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setApiKeyInput('');
                    setGatewayApiKey('');
                    setIsKeyModalOpen(false);
                    success('Key Cleared', 'Using open unauthenticated mode.');
                  }}
                  className="px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  Clear Key
                </button>
                <button
                  type="submit"
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  <Check className="w-3.5 h-3.5" />
                  Save Key
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
