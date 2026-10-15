// ── Enums ────────────────────────────────────────────────────────────────────

export type WorkflowStatus = 'draft' | 'active' | 'paused' | 'archived'

export type NodeType =
  | 'trigger'
  | 'action'
  | 'condition'
  | 'agent'
  | 'transform'
  | 'output'

export type ExecutionStatus =
  | 'pending'
  | 'running'
  | 'success'
  | 'failed'
  | 'cancelled'

// ── AgentConfig ───────────────────────────────────────────────────────────────

export interface AgentConfigCreate {
  model_provider: string
  model_name: string
  model_version?: string | null
  system_prompt?: string | null
  temperature?: number
  max_tokens?: number
  tools?: Record<string, unknown>[] | null
  mlflow_experiment_id?: string | null
}

export interface AgentConfigUpdate extends Partial<AgentConfigCreate> {}

export interface AgentConfigResponse {
  id: string
  node_id: string
  model_provider: string
  model_name: string
  model_version: string | null
  system_prompt: string | null
  temperature: number
  max_tokens: number
  tools: Record<string, unknown>[] | null
  mlflow_experiment_id: string | null
  created_at: string
  updated_at: string
}

// ── Node ─────────────────────────────────────────────────────────────────────

export interface NodeCreate {
  name: string
  node_type: NodeType
  position_x?: number | null
  position_y?: number | null
  config?: Record<string, unknown> | null
  next_nodes?: string[] | null
  order?: number
  agent_config?: AgentConfigCreate | null
}

export interface NodeUpdate {
  name?: string
  node_type?: NodeType
  position_x?: number | null
  position_y?: number | null
  config?: Record<string, unknown> | null
  next_nodes?: string[] | null
  order?: number
}

export interface NodeResponse {
  id: string
  workflow_id: string
  name: string
  node_type: NodeType
  position_x: number | null
  position_y: number | null
  config: Record<string, unknown> | null
  next_nodes: string[] | null
  order: number
  agent_config: AgentConfigResponse | null
  created_at: string
  updated_at: string
}

// ── Workflow ──────────────────────────────────────────────────────────────────

export interface WorkflowCreate {
  name: string
  description?: string | null
  status?: WorkflowStatus
  is_active?: boolean
  meta?: Record<string, unknown> | null
  nodes?: NodeCreate[]
}

export interface WorkflowUpdate {
  name?: string
  description?: string | null
  status?: WorkflowStatus
  is_active?: boolean
  meta?: Record<string, unknown> | null
}

export interface WorkflowSummary {
  id: string
  name: string
  description: string | null
  status: WorkflowStatus
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface WorkflowResponse {
  id: string
  name: string
  description: string | null
  status: WorkflowStatus
  is_active: boolean
  meta: Record<string, unknown> | null
  nodes: NodeResponse[]
  created_at: string
  updated_at: string
}

export interface PaginatedWorkflows {
  total: number
  page: number
  page_size: number
  items: WorkflowSummary[]
}

// ── ExecutionLog ──────────────────────────────────────────────────────────────

export interface ExecutionStep {
  node_id: string
  node_name?: string
  status: ExecutionStatus
  duration_ms?: number
  output?: Record<string, unknown>
  error?: string
}

export interface ExecutionLogResponse {
  id: string
  workflow_id: string
  status: ExecutionStatus
  trigger_payload: Record<string, unknown> | null
  output: Record<string, unknown> | null
  error_message: string | null
  steps: ExecutionStep[] | null
  duration_ms: number | null
  mlflow_run_id: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

// ── React Flow canvas types ───────────────────────────────────────────────────

export interface FlowNodeData {
  label: string
  node_type: NodeType
  config: Record<string, unknown> | null
  agent_config?: AgentConfigResponse | null
  /** Backend persisted ID — undefined for new unsaved nodes */
  backendId?: string
}
