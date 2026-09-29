import React, { useState, useEffect } from 'react';
import {
  AgentDefinitionResponse,
  AgentTaskResponse,
  WorkspaceResponse
} from '../../types';
import { api } from '../../services/api';
import {
  Bot,
  Play,
  CheckCircle2,
  Loader2,
  Code2,
  BookOpen,
  LineChart,
  Briefcase,
  Sparkles,
  Database,
  Globe,
  Check,
  Copy,
  Wrench,
  History
} from 'lucide-react';

interface AgentHubViewProps {
  activeWorkspace: WorkspaceResponse | null;
}

export const AgentHubView: React.FC<AgentHubViewProps> = ({ activeWorkspace }) => {
  const [agents, setAgents] = useState<AgentDefinitionResponse[]>([]);
  const [selectedAgentSlug, setSelectedAgentSlug] = useState<string>('coder-agent');
  const [goalPrompt, setGoalPrompt] = useState<string>('');
  const [useRAG, setUseRAG] = useState<boolean>(true);
  const [useWebSearch, setUseWebSearch] = useState<boolean>(false);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [currentTask, setCurrentTask] = useState<AgentTaskResponse | null>(null);
  const [taskHistory, setTaskHistory] = useState<AgentTaskResponse[]>([]);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    loadAgents();
    loadTaskHistory();
  }, [activeWorkspace?.slug]);

  const loadAgents = async () => {
    try {
      const list = await api.getAgents(activeWorkspace?.slug);
      setAgents(list);
      if (list.length > 0 && !list.some((a) => a.slug === selectedAgentSlug)) {
        setSelectedAgentSlug(list[0].slug);
      }
    } catch (err) {
      console.error('Failed to load agents:', err);
    }
  };

  const loadTaskHistory = async () => {
    try {
      const history = await api.getAgentTasks(activeWorkspace?.slug);
      setTaskHistory(history);
    } catch (err) {
      console.warn('Failed to load task history:', err);
    }
  };

  const handleLaunchAgentTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalPrompt.trim() || isRunning) return;

    setIsRunning(true);
    setCurrentTask(null);

    try {
      const task = await api.createAgentTask({
        agent_slug: selectedAgentSlug,
        goal_prompt: goalPrompt.trim(),
        workspace_slug: activeWorkspace?.slug || 'general',
        use_rag: useRAG,
        use_web_search: useWebSearch,
      });
      setCurrentTask(task);
      setTaskHistory((prev) => [task, ...prev]);
    } catch (err: any) {
      console.error('Agent task launch error:', err);
      alert(`Agent execution failed: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  };

  const handleCopyDeliverable = () => {
    if (currentTask?.result_output) {
      navigator.clipboard.writeText(currentTask.result_output);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getAgentIcon = (role: string) => {
    switch (role) {
      case 'coder':
        return <Code2 className="w-5 h-5 text-[#34888D]" />;
      case 'researcher':
        return <BookOpen className="w-5 h-5 text-[#34888D]" />;
      case 'analyst':
        return <LineChart className="w-5 h-5 text-[#34888D]" />;
      case 'executive':
        return <Briefcase className="w-5 h-5 text-[#34888D]" />;
      default:
        return <Bot className="w-5 h-5 text-[#34888D]" />;
    }
  };

  const selectedAgent = agents.find((a) => a.slug === selectedAgentSlug) || agents[0];

  return (
    <div className="flex h-full bg-[#000000] text-white overflow-hidden">
      {/* Role Agents Selection & History Sidebar */}
      <div className="w-80 border-r border-[#2a2928] bg-[#000000] flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-[#2a2928] flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Bot className="w-4 h-4 text-[#34888D]" />
            <span className="text-xs font-semibold text-[#949494] uppercase tracking-wider">
              Autonomous Agents
            </span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-[11px] bg-[#016A71]/20 text-[#34888D] border border-[#016A71]/40 font-mono">
            Autonomous
          </span>
        </div>

        {/* Agent Cards */}
        <div className="p-3 border-b border-[#2a2928] space-y-2">
          <span className="text-[11px] font-semibold text-[#949494] uppercase tracking-wider px-1 block">
            Select Role Agent
          </span>
          <div className="space-y-1.5">
            {agents.map((agent) => {
              const isSelected = agent.slug === selectedAgentSlug;
              return (
                <div
                  key={agent.id}
                  onClick={() => setSelectedAgentSlug(agent.slug)}
                  className={`p-3 rounded-[11px] cursor-pointer transition-all border ${
                    isSelected
                      ? 'bg-[#171615] border-[#016A71]/60 text-white shadow-[0_0_12px_rgba(1,106,113,0.15)]'
                      : 'bg-[#171615]/50 border-[#2a2928] text-[#949494] hover:bg-[#171615] hover:text-white'
                  }`}
                >
                  <div className="flex items-center space-x-2.5 mb-1.5">
                    {getAgentIcon(agent.role_type)}
                    <span className="font-semibold text-xs text-white truncate">{agent.name}</span>
                  </div>
                  <p className="text-[11px] text-[#949494] line-clamp-2 leading-snug">
                    {agent.description}
                  </p>
                  <div className="flex items-center justify-between mt-2 pt-2 border-t border-[#2a2928] text-[10px] text-[#949494] font-mono">
                    <span>{agent.allowed_tools.length} Tools</span>
                    <span className="text-[#34888D]">{agent.max_steps} Max Steps</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Historical Tasks */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <span className="text-[11px] font-semibold text-[#949494] uppercase tracking-wider px-1 flex items-center space-x-1.5">
            <History className="w-3.5 h-3.5 text-[#34888D]" />
            <span>Task History ({taskHistory.length})</span>
          </span>

          {taskHistory.length === 0 ? (
            <div className="p-6 text-center text-[#949494] text-xs">
              No tasks launched yet in this workspace.
            </div>
          ) : (
            <div className="space-y-1">
              {taskHistory.map((task) => (
                <div
                  key={task.id}
                  onClick={async () => {
                    const full = await api.getAgentTask(task.id);
                    setCurrentTask(full);
                  }}
                  className={`p-2.5 rounded-[11px] cursor-pointer transition-all text-xs border ${
                    currentTask?.id === task.id
                      ? 'bg-[#171615] border-[#016A71]/60 text-white font-medium shadow-[0_0_10px_rgba(1,106,113,0.15)]'
                      : 'bg-[#171615]/50 border-[#2a2928] text-[#949494] hover:bg-[#171615] hover:text-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="truncate font-medium text-[11px]">{task.title}</span>
                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded-[11px] font-mono ${
                        task.status === 'completed'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                      }`}
                    >
                      {task.status}
                    </span>
                  </div>
                  <div className="text-[10px] text-[#949494] font-mono">
                    {new Date(task.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Agent Workspace */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#000000] overflow-y-auto p-6 space-y-6">
        {/* Active Agent Banner */}
        {selectedAgent && (
          <div className="p-5 rounded-[11px] bg-[#171615] border border-[#2a2928] shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="flex items-center space-x-3.5">
              <div className="w-11 h-11 rounded-[11px] bg-[#016A71]/15 border border-[#016A71]/30 flex items-center justify-center">
                {getAgentIcon(selectedAgent.role_type)}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-base font-bold text-white tracking-tight">{selectedAgent.name}</h2>
                  <span className="text-[10px] px-2 py-0.5 rounded-[11px] bg-[#222120] border border-[#2a2928] text-[#949494] font-mono">
                    {selectedAgent.preferred_model_id}
                  </span>
                </div>
                <p className="text-xs text-[#949494] mt-0.5">{selectedAgent.description}</p>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <div className="flex items-center space-x-1.5 text-xs text-[#949494]">
                <Wrench className="w-3.5 h-3.5 text-[#34888D]" />
                <span>Allowed Tools:</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {selectedAgent.allowed_tools.map((tool) => (
                  <span key={tool} className="text-[10px] px-2 py-0.5 rounded-[11px] bg-[#222120] border border-[#2a2928] font-mono text-white">
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Launch Goal Form */}
        <form onSubmit={handleLaunchAgentTask} className="bg-[#171615] border border-[#2a2928] rounded-[11px] p-5 shadow-sm space-y-3">
          <label className="text-xs font-semibold text-[#949494] uppercase tracking-wider block">
            Define Autonomous Goal / Requirement
          </label>
          <div className="relative">
            <textarea
              rows={3}
              required
              value={goalPrompt}
              onChange={(e) => setGoalPrompt(e.target.value)}
              placeholder={`Describe what you want ${selectedAgent?.name || 'this agent'} to accomplish (e.g. 'Synthesize a data pipeline, validate schema with tools, and generate test assertions')...`}
              className="w-full bg-[#201f1e] border border-[#2a2928] rounded-[11px] p-3 text-xs text-white placeholder-[#949494] focus:outline-none focus:border-[#34888D]/70 resize-none"
            />
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-1">
            <div className="flex items-center space-x-3 text-xs">
              <label className="flex items-center space-x-1.5 cursor-pointer text-[#949494] hover:text-white">
                <input
                  type="checkbox"
                  checked={useRAG}
                  onChange={(e) => setUseRAG(e.target.checked)}
                  className="rounded accent-[#016A71]"
                />
                <Database className="w-3.5 h-3.5 text-[#34888D]" />
                <span>Vector RAG Knowledge</span>
              </label>

              <label className="flex items-center space-x-1.5 cursor-pointer text-[#949494] hover:text-white">
                <input
                  type="checkbox"
                  checked={useWebSearch}
                  onChange={(e) => setUseWebSearch(e.target.checked)}
                  className="rounded accent-[#016A71]"
                />
                <Globe className="w-3.5 h-3.5 text-[#34888D]" />
                <span>Live Web Research</span>
              </label>
            </div>

            <button
              type="submit"
              disabled={!goalPrompt.trim() || isRunning}
              className="w-full sm:w-auto px-5 py-2.5 rounded-[11px] bg-[#016A71] hover:bg-[#01575d] text-white text-xs font-semibold shadow-[0_0_12px_rgba(1,106,113,0.3)] flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
            >
              {isRunning ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Agent Reasoning in Progress...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span>Execute Autonomous Task</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Task Execution Output & Step Trace */}
        {isRunning && (
          <div className="p-8 rounded-[11px] bg-[#171615] border border-[#016A71]/40 text-center space-y-3">
            <Loader2 className="w-8 h-8 text-[#34888D] animate-spin mx-auto" />
            <h4 className="text-sm font-semibold text-white">
              {selectedAgent?.name} is executing autonomous loop...
            </h4>
            <p className="text-xs text-[#949494] max-w-md mx-auto">
              Generating plan, invoking sandboxed tools, cross-referencing PostgreSQL vector data, and reflecting on deliverable.
            </p>
          </div>
        )}

        {currentTask && !isRunning && (
          <div className="space-y-6">
            {/* Step Trace Timeline */}
            <div className="bg-[#171615] border border-[#2a2928] rounded-[11px] p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#2a2928]">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-[#34888D]" />
                  <span className="text-xs font-semibold text-white uppercase tracking-wider">
                    Autonomous Reasoning Trace ({currentTask.steps.length} Steps)
                  </span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-[11px] bg-emerald-500/10 text-emerald-400 font-mono border border-emerald-500/20">
                  {currentTask.status.toUpperCase()}
                </span>
              </div>

              <div className="space-y-3">
                {currentTask.steps.map((step) => (
                  <div
                    key={step.id || step.step_index}
                    className="p-3.5 rounded-[11px] bg-black/40 border border-[#2a2928] space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-[11px] font-mono uppercase font-semibold ${
                            step.step_type === 'plan'
                              ? 'bg-[#016A71]/20 text-[#34888D] border border-[#016A71]/35'
                              : step.step_type === 'tool_call'
                              ? 'bg-[#34888D]/20 text-[#34888D] border border-[#34888D]/40'
                              : step.step_type === 'observation'
                              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              : step.step_type === 'reflection'
                              ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20'
                              : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          }`}
                        >
                          Step {step.step_index}: {step.step_type}
                        </span>
                        {step.tool_name && (
                          <span className="text-[11px] text-[#949494] font-mono">
                            Tool: {step.tool_name}
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-[#949494] font-mono">
                        {step.duration_ms}ms
                      </span>
                    </div>

                    <p className="text-white leading-relaxed whitespace-pre-wrap">{step.content}</p>

                    {step.tool_result && Object.keys(step.tool_result).length > 0 && (
                      <pre className="p-2.5 rounded-[11px] bg-[#171615] border border-[#2a2928] text-[11px] text-[#34888D] font-mono overflow-x-auto">
                        {JSON.stringify(step.tool_result, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Final Deliverable Card */}
            {currentTask.result_output && (
              <div className="bg-[#171615] border border-[#016A71]/50 rounded-[11px] p-6 shadow-xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#2a2928]">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-[#34888D]" />
                    <span className="text-xs font-semibold text-white uppercase tracking-wider">
                      Verified Agent Deliverable
                    </span>
                  </div>
                  <button
                    onClick={handleCopyDeliverable}
                    className="flex items-center space-x-1 px-3 py-1.5 rounded-[11px] bg-[#222120] hover:bg-[#2c2b2a] text-[#949494] hover:text-white text-xs font-medium transition-colors border border-[#2a2928]"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="text-emerald-400">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy Deliverable</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="prose prose-invert max-w-none text-xs leading-relaxed whitespace-pre-wrap text-white">
                  {currentTask.result_output}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
