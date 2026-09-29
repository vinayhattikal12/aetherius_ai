import React, { useState, useEffect } from 'react';
import {
  ToolDefinition,
  ToolExecutionResponse,
  WorkspaceResponse
} from '../../types';
import { api } from '../../services/api';
import {
  Wrench,
  Play,
  Calculator,
  Code2,
  KeyRound,
  DollarSign,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Clock
} from 'lucide-react';

interface ToolsViewProps {
  activeWorkspace: WorkspaceResponse | null;
}

export const ToolsView: React.FC<ToolsViewProps> = ({ activeWorkspace }) => {
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [selectedToolName, setSelectedToolName] = useState<string>('calculate_expression');
  const [paramValues, setParamValues] = useState<Record<string, any>>({
    expression: '(24 * 60) + (10 ** 3)',
  });
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [executionResult, setExecutionResult] = useState<ToolExecutionResponse | null>(null);

  useEffect(() => {
    loadTools();
  }, [activeWorkspace?.slug]);

  const loadTools = async () => {
    try {
      const list = await api.getWorkspaceTools(activeWorkspace?.slug);
      setTools(list);
      if (list.length > 0) {
        setSelectedToolName(list[0].name);
        initParams(list[0]);
      }
    } catch (err) {
      console.error('Failed to load tools:', err);
    }
  };

  const initParams = (tool: ToolDefinition) => {
    const defaults: Record<string, any> = {};
    tool.parameters.forEach((p) => {
      if (p.name === 'expression') defaults[p.name] = '(1024 * 4) + (2 ** 8)';
      else if (p.name === 'raw_json') defaults[p.name] = '{"service":"Aetherius","status":"online","port":8000}';
      else if (p.name === 'pattern') defaults[p.name] = '\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,7}\\b';
      else if (p.name === 'text') defaults[p.name] = 'Contact us at team@aetherius.ai or support@example.org for assistance.';
      else if (p.name === 'data') defaults[p.name] = 'Aetherius Intelligence Platform';
      else if (p.name === 'principal') defaults[p.name] = 25000;
      else if (p.name === 'annual_rate_percent') defaults[p.name] = 7.5;
      else if (p.name === 'years') defaults[p.name] = 5;
      else defaults[p.name] = p.default !== undefined ? p.default : '';
    });
    setParamValues(defaults);
    setExecutionResult(null);
  };

  const handleSelectTool = (tool: ToolDefinition) => {
    setSelectedToolName(tool.name);
    initParams(tool);
  };

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsExecuting(true);
    try {
      const res = await api.executeTool({
        tool_name: selectedToolName,
        arguments: paramValues,
        workspace_slug: activeWorkspace?.slug || 'general',
      });
      setExecutionResult(res);
    } catch (err: any) {
      console.error('Tool execution error:', err);
    } finally {
      setIsExecuting(false);
    }
  };

  const selectedTool = tools.find((t) => t.name === selectedToolName) || tools[0];

  const getToolIcon = (cat: string) => {
    switch (cat) {
      case 'math':
        return <Calculator className="w-4 h-4 text-[#34888D]" />;
      case 'code':
        return <Code2 className="w-4 h-4 text-[#34888D]" />;
      case 'system':
        return <KeyRound className="w-4 h-4 text-amber-400" />;
      case 'finance':
        return <DollarSign className="w-4 h-4 text-[#34888D]" />;
      default:
        return <Wrench className="w-4 h-4 text-[#34888D]" />;
    }
  };

  return (
    <div className="flex h-full bg-[#000000] text-white overflow-hidden">
      {/* Tools Directory Sidebar */}
      <div className="w-72 border-r border-[#2a2928] bg-[#000000] flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-[#2a2928] flex items-center space-x-2">
          <Wrench className="w-4 h-4 text-[#34888D]" />
          <span className="text-xs font-semibold text-[#949494] uppercase tracking-wider">
            Workspace Tools
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {tools.map((t) => {
            const isSelected = t.name === selectedToolName;
            return (
              <div
                key={t.name}
                onClick={() => handleSelectTool(t)}
                className={`p-3 rounded-[11px] cursor-pointer transition-all border ${
                  isSelected
                    ? 'bg-[#171615] border-[#016A71]/60 text-white shadow-[0_0_12px_rgba(1,106,113,0.15)]'
                    : 'bg-[#171615]/50 border-[#2a2928] text-[#949494] hover:bg-[#171615] hover:text-white'
                }`}
              >
                <div className="flex items-center space-x-2 mb-1">
                  {getToolIcon(t.category)}
                  <span className="font-medium text-xs text-white truncate">{t.display_name}</span>
                </div>
                <p className="text-[11px] text-[#949494] line-clamp-2">{t.description}</p>
              </div>
            );
          })}
        </div>

        <div className="p-3 border-t border-[#2a2928] bg-[#171615] text-[11px] text-[#949494] font-mono">
          <span>Sandboxed AST Execution</span>
        </div>
      </div>

      {/* Main Tool Execution Playground */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#000000] overflow-y-auto p-6">
        {selectedTool ? (
          <div className="max-w-4xl mx-auto w-full space-y-6">
            {/* Header */}
            <div className="pb-4 border-b border-[#2a2928]">
              <div className="flex items-center space-x-2.5">
                <div className="w-9 h-9 rounded-[11px] bg-[#171615] border border-[#2a2928] flex items-center justify-center">
                  {getToolIcon(selectedTool.category)}
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white tracking-tight">{selectedTool.display_name}</h2>
                  <p className="text-xs text-[#949494] mt-0.5">{selectedTool.description}</p>
                </div>
              </div>
            </div>

            {/* Execution Form */}
            <form onSubmit={handleExecute} className="bg-[#171615] border border-[#2a2928] rounded-[11px] p-5 space-y-4">
              <h3 className="text-xs font-semibold text-[#949494] uppercase tracking-wider">
                Tool Parameters
              </h3>

              <div className="space-y-3">
                {selectedTool.parameters.map((param) => (
                  <div key={param.name}>
                    <label className="text-xs font-medium text-white block mb-1">
                      {param.name} {param.required && <span className="text-rose-400">*</span>}
                      <span className="text-[10px] text-[#949494] ml-2 font-mono">({param.type})</span>
                    </label>
                    {param.name === 'text' || param.name === 'raw_json' ? (
                      <textarea
                        rows={3}
                        required={param.required}
                        value={paramValues[param.name] || ''}
                        onChange={(e) =>
                          setParamValues({ ...paramValues, [param.name]: e.target.value })
                        }
                        className="w-full bg-[#201f1e] border border-[#2a2928] rounded-[11px] p-2.5 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70 font-mono resize-none"
                      />
                    ) : (
                      <input
                        type={param.type === 'number' || param.type === 'integer' ? 'number' : 'text'}
                        step={param.type === 'number' ? 'any' : undefined}
                        required={param.required}
                        value={paramValues[param.name] ?? ''}
                        onChange={(e) =>
                          setParamValues({
                            ...paramValues,
                            [param.name]:
                              param.type === 'number' || param.type === 'integer'
                                ? parseFloat(e.target.value) || 0
                                : e.target.value,
                          })
                        }
                        className="w-full bg-[#201f1e] border border-[#2a2928] rounded-[11px] px-3 py-2 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70 font-mono"
                      />
                    )}
                    <span className="text-[10px] text-[#949494] mt-1 block">
                      {param.description}
                    </span>
                  </div>
                ))}
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={isExecuting}
                  className="flex items-center space-x-2 px-4 py-2 rounded-[11px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-semibold shadow-[0_0_12px_rgba(1,106,113,0.3)] transition-all disabled:opacity-50"
                >
                  {isExecuting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5" />
                  )}
                  <span>Run Sandboxed Tool</span>
                </button>
              </div>
            </form>

            {/* Execution Result */}
            {executionResult && (
              <div className="bg-[#171615] border border-[#2a2928] rounded-[11px] p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {executionResult.status === 'success' ? (
                      <CheckCircle className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-rose-400" />
                    )}
                    <span className="text-xs font-semibold text-white uppercase tracking-wider">
                      Execution Result ({executionResult.status})
                    </span>
                  </div>
                  <div className="flex items-center space-x-1 text-[11px] text-[#949494] font-mono">
                    <Clock className="w-3 h-3" />
                    <span>{executionResult.execution_time_ms} ms</span>
                  </div>
                </div>

                {executionResult.error_message ? (
                  <div className="p-3 rounded-[11px] bg-rose-950/40 border border-rose-800/40 text-rose-400 text-xs">
                    {executionResult.error_message}
                  </div>
                ) : (
                  <pre className="p-3.5 rounded-[11px] bg-black/40 border border-[#2a2928] text-xs text-[#34888D] font-mono overflow-x-auto whitespace-pre-wrap">
                    {typeof executionResult.result === 'object'
                      ? JSON.stringify(executionResult.result, null, 2)
                      : String(executionResult.result)}
                  </pre>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center p-8">
            <Wrench className="w-10 h-10 text-[#949494]/40 mb-3" />
            <h3 className="text-sm font-semibold text-white">No Tool Selected</h3>
          </div>
        )}
      </div>
    </div>
  );
};
