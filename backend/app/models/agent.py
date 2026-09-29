from sqlalchemy import String, Integer, Float, Text, ForeignKey, JSON, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from backend.app.models.base import BaseModel


class AgentDefinition(BaseModel):
    __tablename__ = "agent_definitions"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    role_type: Mapped[str] = mapped_column(String(50), nullable=False)  # coder, researcher, analyst, executive, custom
    workspace_slug: Mapped[str] = mapped_column(String(50), default="general", nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    system_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_tools: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    preferred_model_id: Mapped[str] = mapped_column(String(100), default="llama3.2:3b", nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Relationships
    tasks = relationship("AgentTask", back_populates="agent_definition", cascade="all, delete-orphan")


class AgentTask(BaseModel):
    __tablename__ = "agent_tasks"

    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_slug: Mapped[str] = mapped_column(String(50), default="general", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)  # pending, planning, running, completed, failed
    result_output: Mapped[str] = mapped_column(Text, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    execution_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent_definition = relationship("AgentDefinition", back_populates="tasks")
    steps = relationship("AgentTaskStep", back_populates="task", cascade="all, delete-orphan", order_by="AgentTaskStep.step_index")


class AgentTaskStep(BaseModel):
    __tablename__ = "agent_task_steps"

    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(30), nullable=False)  # plan, tool_call, observation, reflection, final_output
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=True)
    tool_arguments: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)
    tool_result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    task = relationship("AgentTask", back_populates="steps")
