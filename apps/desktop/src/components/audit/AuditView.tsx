import React, { useState, useEffect } from 'react';
import {
  AuditLogResponse,
  SystemDiagnosticsResponse,
  WorkspaceResponse
} from '../../types';
import { api } from '../../services/api';
import {
  ShieldCheck,
  Activity,
  Database,
  HardDrive,
  Cpu,
  RefreshCw,
  Search,
  Server
} from 'lucide-react';

interface AuditViewProps {
  activeWorkspace: WorkspaceResponse | null;
}

export const AuditView: React.FC<AuditViewProps> = () => {
  const [logs, setLogs] = useState<AuditLogResponse[]>([]);
  const [diagnostics, setDiagnostics] = useState<SystemDiagnosticsResponse | null>(null);
  const [selectedEventType, setSelectedEventType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    loadData();
  }, [selectedEventType]);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const typeFilter = selectedEventType === 'all' ? undefined : selectedEventType;
      const [logList, diag] = await Promise.all([
        api.getAuditLogs(typeFilter),
        api.getDiagnostics(),
      ]);
      setLogs(logList);
      setDiagnostics(diag);
    } catch (err) {
      console.error('Failed to load audit & diagnostics:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredLogs = logs.filter(
    (l) =>
      l.event_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      l.actor.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-full bg-[#000000] text-white flex-col overflow-hidden">
      {/* Top Header */}
      <div className="p-6 border-b border-[#2a2928] bg-[#000000] flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-[11px] bg-[#016A71]/15 border border-[#016A71]/30 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-[#34888D]" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-lg font-bold text-white tracking-tight">Security, Audit & System Health</h2>
              <span className="text-[10px] px-2 py-0.5 rounded-[11px] bg-[#016A71]/20 text-[#34888D] border border-[#016A71]/40 font-mono">
                PostgreSQL Compliance
              </span>
            </div>
            <p className="text-xs text-[#949494]">
              Immutable logging of completions, tool operations, PII masking, and real-time infrastructure telemetry.
            </p>
          </div>
        </div>

        <button
          onClick={loadData}
          disabled={isLoading}
          className="flex items-center space-x-2 px-4 py-2 rounded-[11px] bg-[#171615] hover:bg-[#201f1e] text-white border border-[#2a2928] text-xs font-medium transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Diagnostics</span>
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* System Diagnostics Health Cards */}
        {diagnostics && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Database Card */}
            <div className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-xs font-semibold text-white">
                  <Database className="w-4 h-4 text-[#34888D]" />
                  <span>Database</span>
                </div>
                <span className="text-[10px] px-1.5 py-0.5 rounded-[11px] bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">
                  {diagnostics.components.database.status.toUpperCase()}
                </span>
              </div>
              <div className="text-xs text-white font-mono">
                PostgreSQL (pgvector)
              </div>
              <div className="text-[10px] text-[#949494] font-mono">
                Port: {diagnostics.components.database.port} • Local
              </div>
            </div>

            {/* Storage Card */}
            <div className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-xs font-semibold text-white">
                  <HardDrive className="w-4 h-4 text-[#34888D]" />
                  <span>Storage</span>
                </div>
                <span className="text-[10px] px-1.5 py-0.5 rounded-[11px] bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">
                  {diagnostics.components.storage.status.toUpperCase()}
                </span>
              </div>
              <div className="text-xs text-white font-mono">
                {diagnostics.components.storage.free_gb ?? 0} GB Free
              </div>
              <div className="text-[10px] text-[#949494] font-mono truncate">
                {diagnostics.components.storage.storage_path}
              </div>
            </div>

            {/* Local AI Server */}
            <div className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-xs font-semibold text-white">
                  <Server className="w-4 h-4 text-amber-400" />
                  <span>Local AI Daemon</span>
                </div>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-[11px] font-mono ${
                    diagnostics.components.local_ai_server.status === 'online'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-[#222120] text-[#949494]'
                  }`}
                >
                  {diagnostics.components.local_ai_server.status.toUpperCase()}
                </span>
              </div>
              <div className="text-xs text-white font-mono">
                {diagnostics.components.local_ai_server.provider}
              </div>
              <div className="text-[10px] text-[#949494] font-mono">
                {diagnostics.components.local_ai_server.models_installed?.length || 0} Models Installed
              </div>
            </div>

            {/* Compute Tier */}
            <div className="p-4 rounded-[11px] bg-[#171615] border border-[#2a2928] space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-xs font-semibold text-white">
                  <Cpu className="w-4 h-4 text-[#34888D]" />
                  <span>Compute Tier</span>
                </div>
                <span className="text-[10px] px-1.5 py-0.5 rounded-[11px] bg-[#016A71]/20 text-[#34888D] border border-[#016A71]/40 font-mono">
                  {diagnostics.components.hardware.compute_tier}
                </span>
              </div>
              <div className="text-xs text-white font-mono truncate">
                {diagnostics.components.hardware.cpu}
              </div>
              <div className="text-[10px] text-[#949494] font-mono">
                RAM: {diagnostics.components.hardware.ram_gb}GB • VRAM: {diagnostics.components.hardware.vram_gb}GB
              </div>
            </div>
          </div>
        )}

        {/* Audit Log Stream */}
        <div className="bg-[#171615] border border-[#2a2928] rounded-[11px] p-5 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between pb-3 border-b border-[#2a2928] gap-3">
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4 text-[#34888D]" />
              <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
                Audit Trail ({filteredLogs.length} Events)
              </h3>
            </div>

            <div className="flex items-center space-x-2 w-full sm:w-auto">
              <div className="relative flex-1 sm:w-64">
                <Search className="w-3.5 h-3.5 text-[#949494] absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  placeholder="Filter events..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-[#201f1e] border border-[#2a2928] rounded-[11px] pl-8 pr-2 py-1.5 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70"
                />
              </div>

              <select
                value={selectedEventType}
                onChange={(e) => setSelectedEventType(e.target.value)}
                className="bg-[#201f1e] border border-[#2a2928] rounded-[11px] px-2.5 py-1.5 text-xs text-white focus:outline-none"
              >
                <option value="all" className="bg-[#171615] text-white">All Events</option>
                <option value="security_pii_masked" className="bg-[#171615] text-white">PII Masking</option>
                <option value="chat_completion" className="bg-[#171615] text-white">Completions</option>
                <option value="tool_execution" className="bg-[#171615] text-white">Tool Execution</option>
                <option value="agent_task_executed" className="bg-[#171615] text-white">Agent Tasks</option>
              </select>
            </div>
          </div>

          {filteredLogs.length === 0 ? (
            <div className="p-8 text-center text-[#949494] text-xs">
              No audit events found matching filters.
            </div>
          ) : (
            <div className="divide-y divide-[#2a2928]">
              {filteredLogs.map((log) => (
                <div key={log.id} className="py-3 flex flex-col space-y-1.5 hover:bg-[#201f1e] px-2 rounded-[11px] transition-colors">
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] px-2 py-0.5 rounded-[11px] font-mono font-semibold bg-[#222120] text-[#949494] border border-[#2a2928]">
                        {log.event_type}
                      </span>
                      <span className="text-[#949494] text-xs">
                        Actor: <span className="text-white font-medium">{log.actor}</span>
                      </span>
                    </div>

                    <div className="flex items-center space-x-2 text-[10px] text-[#949494] font-mono">
                      <span>{new Date(log.created_at).toLocaleString()}</span>
                    </div>
                  </div>

                  {log.details && Object.keys(log.details).length > 0 && (
                    <pre className="p-2.5 rounded-[11px] bg-black/40 border border-[#2a2928] text-[10px] text-[#949494] font-mono overflow-x-auto">
                      {JSON.stringify(log.details, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
