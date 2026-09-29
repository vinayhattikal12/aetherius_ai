import React, { useEffect, useState } from 'react';
import { api } from './services/api';
import {
  HardwareProfile,
  ModelResponse,
  ModelPackageResponse,
  WorkspaceResponse,
  UserSettingsResponse,
  ConversationResponse,
} from './types';
import { WelcomeHero } from './components/onboarding/WelcomeHero';
import { SystemAnalyzing } from './components/onboarding/SystemAnalyzing';
import { RecommendedAI } from './components/onboarding/RecommendedAI';
import { WorkspacePicker } from './components/onboarding/WorkspacePicker';
import { Sidebar, NavItem } from './components/layout/Sidebar';
import { TopHeader } from './components/layout/TopHeader';
import { ChatInterface } from './components/chat/ChatInterface';
import { KnowledgeView } from './components/knowledge/KnowledgeView';
import { MemoryView } from './components/memory/MemoryView';
import { ToolsView } from './components/tools/ToolsView';
import { AgentHubView } from './components/agents/AgentHubView';
import { ModelRegistryView } from './components/models/ModelRegistryView';
import { WorkspaceSelectorView } from './components/workspaces/WorkspaceSelectorView';
import { SettingsView } from './components/settings/SettingsView';
import { AuditView } from './components/audit/AuditView';

export const App: React.FC = () => {
  // Navigation & View State
  const [onboardingStep, setOnboardingStep] = useState<number | null>(null);
  const [activeNav, setActiveNav] = useState<NavItem>('chat');
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);

  // Core Intelligence Data
  const [hardwareProfile, setHardwareProfile] = useState<HardwareProfile | null>(null);
  const [isDetectingHardware, setIsDetectingHardware] = useState<boolean>(false);
  const [models, setModels] = useState<ModelResponse[]>([]);
  const [packages, setPackages] = useState<ModelPackageResponse[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [activeWorkspaceSlug, setActiveWorkspaceSlug] = useState<string>('general');
  const [settings, setSettings] = useState<UserSettingsResponse | null>(null);

  // Conversation Management
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  // Initial Boot Lifecycle
  useEffect(() => {
    bootAetherius();
  }, []);

  const bootAetherius = async () => {
    try {
      // 1. Health check backend
      await api.checkHealth();
      setBackendOnline(true);

      // 2. Fetch User Settings
      const userSettings = await api.getSettings();
      setSettings(userSettings);
      const initialWorkspace = userSettings.default_workspace_slug || 'general';
      setActiveWorkspaceSlug(initialWorkspace);

      // 3. Fetch Workspaces & Models
      const [wsList, modelList, pkgList] = await Promise.all([
        api.getWorkspaces(),
        api.getModels(),
        api.getModelPackages(),
      ]);
      setWorkspaces(wsList);
      setModels(modelList);
      setPackages(pkgList);

      // 4. Fetch Conversations for initial workspace
      loadConversations(initialWorkspace);

      // 5. Check if onboarding completed
      if (!userSettings.onboarding_completed) {
        setOnboardingStep(0); // Welcome Hero
      } else {
        setOnboardingStep(null); // Go to main shell
        // Load hardware profile in background
        const profile = await api.detectSystem();
        setHardwareProfile(profile);
      }
    } catch (err) {
      console.warn('Backend connecting or offline mode:', err);
      setBackendOnline(false);
      // Fallback default state for initial launch
      setOnboardingStep(0);
    }
  };

  const loadConversations = async (workspaceSlug?: string) => {
    try {
      const slug = workspaceSlug || activeWorkspaceSlug;
      const list = await api.getConversations(slug);
      setConversations(list);
      if (list.length > 0 && !activeConversationId) {
        setActiveConversationId(list[0].id);
      }
    } catch (err) {
      console.warn('Failed to load conversations:', err);
    }
  };

  useEffect(() => {
    if (backendOnline && activeWorkspaceSlug) {
      loadConversations(activeWorkspaceSlug);
    }
  }, [activeWorkspaceSlug]);

  const handleCreateNewConversation = async () => {
    try {
      const newConv = await api.createConversation(
        'New Session',
        activeWorkspaceSlug || 'general'
      );
      setConversations((prev) => [newConv, ...prev]);
      setActiveConversationId(newConv.id);
      setActiveNav('chat');
    } catch (err) {
      console.error('Failed to create new conversation:', err);
    }
  };

  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        const remaining = conversations.filter((c) => c.id !== convId);
        setActiveConversationId(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const handleStartOnboarding = async () => {
    setOnboardingStep(1); // System Analyzing
    setIsDetectingHardware(true);
    try {
      const profile = await api.detectSystem();
      setHardwareProfile(profile);
      const evaluatedModels = await api.getModels();
      setModels(evaluatedModels);
    } catch (err) {
      console.error('Detection failed:', err);
    } finally {
      setIsDetectingHardware(false);
    }
  };

  const handleReloadModels = async () => {
    try {
      const updatedModels = await api.getModels();
      setModels(updatedModels);
    } catch (err) {
      console.warn('Failed to refresh models:', err);
    }
  };

  const handleToggleModelInstall = async (modelId: string) => {
    try {
      await api.toggleModelInstalled(modelId);
      await handleReloadModels();
    } catch (err) {
      console.error('Toggle install failed:', err);
      await handleReloadModels();
    }
  };

  const handleInstallModel = async (modelId: string) => {
    try {
      await api.installModel(modelId);
      await handleReloadModels();
    } catch (err) {
      console.error('Install model failed:', err);
      await handleReloadModels();
    }
  };

  const handleUninstallModel = async (modelId: string) => {
    try {
      await api.uninstallModel(modelId);
      await handleReloadModels();
    } catch (err) {
      console.error('Uninstall model failed:', err);
      await handleReloadModels();
    }
  };

  const handleCompleteOnboarding = async () => {
    try {
      await api.updateSettings({
        onboarding_completed: true,
        default_workspace_slug: activeWorkspaceSlug,
      });
      await api.saveSystemProfile();
    } catch (err) {
      console.warn('Save settings notice:', err);
    }
    setOnboardingStep(null);
    setActiveNav('chat');
  };

  const handleUpdateSettings = async (updates: Partial<UserSettingsResponse>) => {
    try {
      const updated = await api.updateSettings(updates);
      setSettings(updated);
      if (updates.default_workspace_slug) {
        setActiveWorkspaceSlug(updates.default_workspace_slug);
      }
    } catch (err) {
      console.error('Update settings failed:', err);
      if (settings) {
        setSettings({ ...settings, ...updates });
      }
    }
  };

  const handleToggleTheme = () => {
    const nextTheme = settings?.theme === 'dark' ? 'light' : 'dark';
    handleUpdateSettings({ theme: nextTheme });
  };

  const activeWorkspace =
    workspaces.find((w) => w.slug === activeWorkspaceSlug) || workspaces[0] || null;

  // Onboarding screens
  if (onboardingStep === 0) {
    return <WelcomeHero onStart={handleStartOnboarding} />;
  }

  if (onboardingStep === 1) {
    return (
      <SystemAnalyzing
        profile={hardwareProfile}
        isLoading={isDetectingHardware}
        onNext={() => setOnboardingStep(2)}
        onRetry={handleStartOnboarding}
      />
    );
  }

  if (onboardingStep === 2) {
    return (
      <RecommendedAI
        models={models}
        packages={packages}
        profile={hardwareProfile}
        onToggleInstall={handleInstallModel}
        onNext={() => setOnboardingStep(3)}
        onBack={() => setOnboardingStep(1)}
      />
    );
  }

  if (onboardingStep === 3) {
    return (
      <WorkspacePicker
        workspaces={workspaces}
        selectedSlug={activeWorkspaceSlug}
        onSelect={(slug) => setActiveWorkspaceSlug(slug)}
        onComplete={handleCompleteOnboarding}
        onBack={() => setOnboardingStep(2)}
      />
    );
  }

  const isChatActive = activeNav === 'chat' || activeNav === 'chats';

  // Main Desktop Environment
  return (
    <div className={`flex h-full w-full bg-[#000000] text-white font-sans overflow-hidden ${settings?.theme || 'dark'}`}>
      {/* Primary Unified Sidebar */}
      <Sidebar
        activeNav={activeNav}
        onNavigate={(nav) => setActiveNav(nav)}
        activeWorkspace={activeWorkspace}
        workspaces={workspaces}
        onSelectWorkspace={(slug) => {
          setActiveWorkspaceSlug(slug);
          loadConversations(slug);
          setActiveNav('chat');
        }}
        hardwareProfile={hardwareProfile}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={(id) => {
          setActiveConversationId(id);
          setActiveNav('chat');
        }}
        onCreateNewConversation={handleCreateNewConversation}
        onDeleteConversation={handleDeleteConversation}
        isOpen={isSidebarOpen}
        onToggleOpen={() => setIsSidebarOpen(!isSidebarOpen)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-[#000000]">
        {/* Top Header shown on non-chat management pages */}
        {!isChatActive && (
          <TopHeader
            activeWorkspace={activeWorkspace}
            hardwareProfile={hardwareProfile}
            settings={settings}
            backendOnline={backendOnline}
            onOpenWorkspaces={() => setActiveNav('workspaces')}
            onToggleTheme={handleToggleTheme}
          />
        )}

        <main className="flex-1 overflow-hidden bg-[#000000] flex flex-col">
          {isChatActive && (
            <ChatInterface
              activeWorkspace={activeWorkspace}
              models={models}
              activeConversationId={activeConversationId}
              setActiveConversationId={setActiveConversationId}
              onRefreshConversations={() => loadConversations(activeWorkspaceSlug)}
              isSidebarOpen={isSidebarOpen}
              onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
              onOpenModels={() => setActiveNav('models')}
              onOpenKnowledge={() => setActiveNav('knowledge')}
              onOpenMemory={() => setActiveNav('memory')}
            />
          )}

          {activeNav === 'knowledge' && (
            <div className="flex-1 overflow-y-auto">
              <KnowledgeView activeWorkspace={activeWorkspace} />
            </div>
          )}

          {activeNav === 'memory' && (
            <div className="flex-1 overflow-y-auto">
              <MemoryView activeWorkspace={activeWorkspace} />
            </div>
          )}

          {activeNav === 'tools' && (
            <div className="flex-1 overflow-y-auto">
              <ToolsView activeWorkspace={activeWorkspace} />
            </div>
          )}

          {activeNav === 'models' && (
            <div className="flex-1 overflow-y-auto">
              <ModelRegistryView
                models={models}
                packages={packages}
                profile={hardwareProfile}
                onToggleInstall={handleToggleModelInstall}
                onInstall={handleInstallModel}
                onUninstall={handleUninstallModel}
                onReloadModels={handleReloadModels}
              />
            </div>
          )}

          {activeNav === 'workspaces' && (
            <div className="flex-1 overflow-y-auto">
              <WorkspaceSelectorView
                workspaces={workspaces}
                activeSlug={activeWorkspaceSlug}
                onSelectWorkspace={(slug) => {
                  setActiveWorkspaceSlug(slug);
                  loadConversations(slug);
                  setActiveNav('chat');
                }}
              />
            </div>
          )}

          {activeNav === 'settings' && (
            <div className="flex-1 overflow-y-auto">
              <SettingsView
                settings={settings}
                workspaces={workspaces}
                backendOnline={backendOnline}
                onUpdateSettings={handleUpdateSettings}
                onResetOnboarding={() => setOnboardingStep(0)}
              />
            </div>
          )}

          {activeNav === 'agents' && (
            <div className="flex-1 overflow-y-auto">
              <AgentHubView activeWorkspace={activeWorkspace} />
            </div>
          )}

          {activeNav === 'audit' && (
            <div className="flex-1 overflow-y-auto">
              <AuditView activeWorkspace={activeWorkspace} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
