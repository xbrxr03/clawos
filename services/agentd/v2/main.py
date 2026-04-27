# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Multi-Agent Framework (agentd v2)
====================================
CrewAI-style role-based multi-agent orchestration.

Features:
- Role-based agents (researcher, coder, reviewer, etc.)
- Agent collaboration and delegation
- Structured task workflows
- Agent memory sharing
- Result aggregation
- Hierarchical team structures

Addresses the multi-agent gap from CRITICAL_GAPS_RESEARCH.md
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn

from clawos_core.constants import CLAWOS_DIR, PORT_AGENTD_V2
from clawos_core.config.loader import get as get_config

log = logging.getLogger("agentd_v2")


class AgentRole(Enum):
    """Predefined agent roles with capabilities."""
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    PLANNER = "planner"
    EXECUTOR = "executor"
    ANALYST = "analyst"
    WRITER = "writer"
    MANAGER = "manager"
    CUSTOM = "custom"


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DELEGATED = "delegated"


class MessageType(Enum):
    """Inter-agent message types."""
    REQUEST = "request"
    RESPONSE = "response"
    DELEGATE = "delegate"
    RESULT = "result"
    ERROR = "error"


@dataclass
class AgentCapability:
    """Capability an agent can perform."""
    name: str
    description: str
    tools: List[str] = field(default_factory=list)
    llm_required: bool = True


# Role definitions with default capabilities
ROLE_CAPABILITIES: Dict[AgentRole, List[AgentCapability]] = {
    AgentRole.RESEARCHER: [
        AgentCapability("web_search", "Search the web for information", ["web_search", "browser"]),
        AgentCapability("summarize", "Summarize documents and findings", ["summarize"]),
        AgentCapability("extract_data", "Extract structured data from sources", ["extract"]),
    ],
    AgentRole.CODER: [
        AgentCapability("write_code", "Write code in various languages", ["code_write", "lsp"]),
        AgentCapability("review_code", "Review code for issues", ["code_review"]),
        AgentCapability("debug", "Debug code and find errors", ["debug"]),
        AgentCapability("test", "Write and run tests", ["test"]),
    ],
    AgentRole.REVIEWER: [
        AgentCapability("review", "Review work for quality", ["review"]),
        AgentCapability("feedback", "Provide constructive feedback", []),
        AgentCapability("approve", "Approve or reject work", []),
    ],
    AgentRole.PLANNER: [
        AgentCapability("plan", "Create execution plans", []),
        AgentCapability("break_down", "Break tasks into subtasks", []),
        AgentCapability("prioritize", "Prioritize tasks", []),
    ],
    AgentRole.EXECUTOR: [
        AgentCapability("execute", "Execute commands and scripts", ["shell", "python"]),
        AgentCapability("automate", "Run browser automation", ["browser"]),
        AgentCapability("deploy", "Deploy applications", ["deploy"]),
    ],
    AgentRole.ANALYST: [
        AgentCapability("analyze", "Analyze data and patterns", ["analyze"]),
        AgentCapability("visualize", "Create visualizations", ["chart"]),
        AgentCapability("report", "Generate reports", ["report"]),
    ],
    AgentRole.WRITER: [
        AgentCapability("write", "Write content", ["write"]),
        AgentCapability("edit", "Edit and improve text", ["edit"]),
        AgentCapability("format", "Format documents", ["format"]),
    ],
    AgentRole.MANAGER: [
        AgentCapability("coordinate", "Coordinate team activities", []),
        AgentCapability("delegate", "Delegate tasks to other agents", []),
        AgentCapability("resolve", "Resolve conflicts and blockers", []),
    ],
}


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    role: AgentRole
    goal: str
    backstory: str
    allow_delegation: bool = True
    verbose: bool = True
    llm_model: str = "default"
    max_iterations: int = 5
    tools: List[str] = field(default_factory=list)
    custom_capabilities: List[AgentCapability] = field(default_factory=list)


@dataclass
class Task:
    """A task assigned to an agent."""
    id: str
    description: str
    agent_id: Optional[str] = None
    expected_output: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    subtasks: List["Task"] = field(default_factory=list)
    parent_task_id: Optional[str] = None


@dataclass
class AgentMessage:
    """Message between agents."""
    id: str
    type: MessageType
    from_agent: str
    to_agent: str
    content: str
    task_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Crew:
    """A team of agents working together."""
    id: str
    name: str
    description: str
    agents: List[str] = field(default_factory=list)  # Agent IDs
    tasks: List[str] = field(default_factory=list)  # Task IDs
    process_type: str = "sequential"  # sequential, hierarchical, parallel
    created_at: float = field(default_factory=time.time)


class Agent:
    """
    Role-based AI agent with collaboration capabilities.
    
    Similar to CrewAI agents with:
    - Role definition
    - Goal orientation
    - Tool access
    - Memory/context
    - Delegation capability
    """
    
    def __init__(self, config: AgentConfig, agent_id: Optional[str] = None):
        self.id = agent_id or str(uuid4())
        self.config = config
        self.memory: Dict[str, Any] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Dict[str, Task] = {}
        self.task_history: List[Task] = []
        self.is_running = False
        
        # Get capabilities for role
        self.capabilities = ROLE_CAPABILITIES.get(config.role, []) + config.custom_capabilities
    
    async def execute_task(self, task: Task) -> Task:
        """
        Execute a task.
        
        This is where the actual work happens. In production,
        this would call LLM APIs and tool integrations.
        """
        task.status = TaskStatus.IN_PROGRESS
        task.agent_id = self.id
        task.started_at = time.time()
        self.active_tasks[task.id] = task
        
        log.info(f"Agent {self.config.name} executing task: {task.description}")
        
        try:
            # Simulate work (in production, call LLM/tools)
            result = await self._process_with_llm(task)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
        
        self.active_tasks.pop(task.id, None)
        self.task_history.append(task)
        
        return task
    
    async def _process_with_llm(self, task: Task) -> str:
        """Process task using LLM and available tools."""
        # In production, this would:
        # 1. Build prompt from task + context + memory
        # 2. Call LLM API
        # 3. Execute tool calls if needed
        # 4. Return result
        
        await asyncio.sleep(0.5)  # Simulate processing
        
        return f"[Agent {self.config.name}] Completed: {task.description}\n" \
               f"Using capabilities: {[c.name for c in self.capabilities]}\n" \
               f"Tools available: {self.config.tools}"
    
    async def delegate_task(self, task: Task, to_agent: "Agent") -> Task:
        """Delegate a task to another agent."""
        if not self.config.allow_delegation:
            raise ValueError(f"Agent {self.config.name} cannot delegate")
        
        task.status = TaskStatus.DELEGATED
        task.agent_id = to_agent.id
        
        # Send delegation message
        message = AgentMessage(
            id=str(uuid4()),
            type=MessageType.DELEGATE,
            from_agent=self.id,
            to_agent=to_agent.id,
            content=f"Delegated: {task.description}",
            task_id=task.id
        )
        await to_agent.receive_message(message)
        
        return task
    
    async def receive_message(self, message: AgentMessage):
        """Receive a message from another agent."""
        await self.message_queue.put(message)
        log.info(f"Agent {self.config.name} received {message.type.value} from {message.from_agent}")
    
    async def process_messages(self):
        """Process incoming messages."""
        while self.is_running:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                if message.type == MessageType.DELEGATE:
                    # Execute delegated task
                    task = self.active_tasks.get(message.task_id)
                    if task:
                        await self.execute_task(task)
                
                elif message.type == MessageType.REQUEST:
                    # Handle request
                    pass
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.error(f"Message processing error: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent to dict."""
        return {
            "id": self.id,
            "name": self.config.name,
            "role": self.config.role.value,
            "goal": self.config.goal,
            "backstory": self.config.backstory,
            "capabilities": [c.name for c in self.capabilities],
            "tools": self.config.tools,
            "allow_delegation": self.config.allow_delegation,
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.task_history),
        }


class CrewManager:
    """
    Manager for multi-agent crews.
    
    Orchestrates agent collaboration and task execution.
    """
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.crews: Dict[str, Crew] = {}
        self.tasks: Dict[str, Task] = {}
        self.messages: List[AgentMessage] = []
    
    def create_agent(self, config: AgentConfig) -> Agent:
        """Create a new agent."""
        agent = Agent(config)
        self.agents[agent.id] = agent
        log.info(f"Created agent: {config.name} ({config.role.value})")
        return agent
    
    def create_crew(
        self,
        name: str,
        description: str,
        agents: List[Agent],
        process_type: str = "sequential"
    ) -> Crew:
        """Create a crew from agents."""
        crew = Crew(
            id=str(uuid4()),
            name=name,
            description=description,
            agents=[a.id for a in agents],
            process_type=process_type
        )
        self.crews[crew.id] = crew
        log.info(f"Created crew: {name} with {len(agents)} agents")
        return crew
    
    def create_task(
        self,
        description: str,
        expected_output: str = "",
        agent: Optional[Agent] = None,
        context: Optional[Dict] = None
    ) -> Task:
        """Create a task."""
        task = Task(
            id=str(uuid4()),
            description=description,
            agent_id=agent.id if agent else None,
            expected_output=expected_output,
            context=context or {}
        )
        self.tasks[task.id] = task
        return task
    
    async def execute_crew(
        self,
        crew: Crew,
        tasks: List[Task],
        callback: Optional[Callable[[Task], None]] = None
    ) -> List[Task]:
        """
        Execute all tasks in a crew.
        
        Supports sequential, hierarchical, and parallel execution.
        """
        crew.tasks = [t.id for t in tasks]
        results = []
        
        if crew.process_type == "sequential":
            # Execute tasks in order
            for task in tasks:
                # Assign to first available agent of appropriate role
                agent = self._find_agent_for_task(crew, task)
                if agent:
                    result = await agent.execute_task(task)
                    results.append(result)
                    if callback:
                        callback(result)
                else:
                    task.status = TaskStatus.FAILED
                    task.error = "No suitable agent found"
                    results.append(task)
        
        elif crew.process_type == "hierarchical":
            # Manager agent coordinates
            await self._execute_hierarchical(crew, tasks, results, callback)
        
        elif crew.process_type == "parallel":
            # Execute all tasks in parallel
            coros = []
            for task in tasks:
                agent = self._find_agent_for_task(crew, task)
                if agent:
                    coros.append(agent.execute_task(task))
            
            if coros:
                parallel_results = await asyncio.gather(*coros, return_exceptions=True)
                for result in parallel_results:
                    if isinstance(result, Exception):
                        log.error(f"Task failed: {result}")
                    else:
                        results.append(result)
                        if callback:
                            callback(result)
        
        return results
    
    def _find_agent_for_task(self, crew: Crew, task: Task) -> Optional[Agent]:
        """Find suitable agent for a task."""
        for agent_id in crew.agents:
            agent = self.agents.get(agent_id)
            if agent and len(agent.active_tasks) == 0:
                return agent
        return None
    
    async def _execute_hierarchical(
        self,
        crew: Crew,
        tasks: List[Task],
        results: List[Task],
        callback: Optional[Callable]
    ):
        """Execute with manager coordination."""
        # Find manager agent
        manager = None
        for agent_id in crew.agents:
            agent = self.agents.get(agent_id)
            if agent and agent.config.role == AgentRole.MANAGER:
                manager = agent
                break
        
        if not manager:
            # Fall back to sequential
            for task in tasks:
                agent = self._find_agent_for_task(crew, task)
                if agent:
                    result = await agent.execute_task(task)
                    results.append(result)
                    if callback:
                        callback(result)
            return
        
        # Manager creates plan and delegates
        for task in tasks:
            agent = self._find_agent_for_task(crew, task)
            if agent:
                delegated = await manager.delegate_task(task, agent)
                results.append(delegated)
                if callback:
                    callback(delegated)


# FastAPI models
class AgentConfigModel(BaseModel):
    name: str
    role: str
    goal: str
    backstory: str
    allow_delegation: bool = True
    tools: List[str] = []


class TaskModel(BaseModel):
    description: str
    expected_output: str = ""
    agent_id: Optional[str] = None
    context: Dict[str, Any] = {}


class CrewModel(BaseModel):
    name: str
    description: str
    agent_ids: List[str]
    process_type: str = "sequential"


# FastAPI App
app = FastAPI(title="ClawOS Multi-Agent Framework", version="2.0.0")
manager = CrewManager()


@app.post("/api/v2/agents", response_model=Dict[str, Any])
async def create_agent(config: AgentConfigModel):
    """Create a new agent."""
    agent_config = AgentConfig(
        name=config.name,
        role=AgentRole(config.role),
        goal=config.goal,
        backstory=config.backstory,
        allow_delegation=config.allow_delegation,
        tools=config.tools
    )
    
    agent = manager.create_agent(agent_config)
    return {"success": True, "agent": agent.to_dict()}


@app.get("/api/v2/agents")
async def list_agents():
    """List all agents."""
    return {
        "agents": [a.to_dict() for a in manager.agents.values()]
    }


@app.get("/api/v2/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    agent = manager.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.to_dict()


@app.post("/api/v2/crews")
async def create_crew(crew_data: CrewModel):
    """Create a new crew."""
    agents = [manager.agents.get(aid) for aid in crew_data.agent_ids]
    agents = [a for a in agents if a]  # Filter out missing
    
    if not agents:
        raise HTTPException(status_code=400, detail="No valid agents found")
    
    crew = manager.create_crew(
        name=crew_data.name,
        description=crew_data.description,
        agents=agents,
        process_type=crew_data.process_type
    )
    
    return {
        "success": True,
        "crew": {
            "id": crew.id,
            "name": crew.name,
            "agents": [a.id for a in agents],
            "process_type": crew.process_type
        }
    }


@app.post("/api/v2/tasks")
async def create_task(task_data: TaskModel):
    """Create a new task."""
    agent = manager.agents.get(task_data.agent_id) if task_data.agent_id else None
    
    task = manager.create_task(
        description=task_data.description,
        expected_output=task_data.expected_output,
        agent=agent,
        context=task_data.context
    )
    
    return {
        "success": True,
        "task": {
            "id": task.id,
            "description": task.description,
            "status": task.status.value,
            "agent_id": task.agent_id
        }
    }


@app.post("/api/v2/crews/{crew_id}/execute")
async def execute_crew(crew_id: str, background_tasks: BackgroundTasks):
    """Execute all tasks in a crew."""
    crew = manager.crews.get(crew_id)
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")
    
    tasks = [manager.tasks[tid] for tid in crew.tasks if tid in manager.tasks]
    
    # Execute in background
    async def execute():
        results = await manager.execute_crew(crew, tasks)
        return results
    
    background_tasks.add_task(execute)
    
    return {
        "success": True,
        "message": f"Executing {len(tasks)} tasks in crew {crew.name}",
        "crew_id": crew_id
    }


@app.get("/api/v2/roles")
async def list_roles():
    """List available agent roles."""
    return {
        "roles": [
            {
                "name": role.value,
                "capabilities": [c.name for c in caps]
            }
            for role, caps in ROLE_CAPABILITIES.items()
        ]
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "up",
        "service": "agentd_v2",
        "agents": len(manager.agents),
        "crews": len(manager.crews),
        "tasks": len(manager.tasks)
    }


def run():
    """Run the multi-agent service."""
    config = get_config()
    host = config.get("agentd_v2", {}).get("host", "127.0.0.1")
    port = config.get("agentd_v2", {}).get("port", PORT_AGENTD_V2)
    
    log.info(f"Starting Multi-Agent Framework on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
