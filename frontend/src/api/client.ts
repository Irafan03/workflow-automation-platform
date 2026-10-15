import axios from 'axios'
import type {
  ExecutionLogResponse,
  PaginatedWorkflows,
  WorkflowCreate,
  WorkflowResponse,
  WorkflowUpdate,
} from '@/types'

// ── Axios instance ────────────────────────────────────────────────────────────

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
})

// Response interceptor: unwrap errors into a consistent shape
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail =
      err.response?.data?.detail ??
      err.response?.data?.message ??
      err.message ??
      'Unknown error'
    return Promise.reject(new Error(String(detail)))
  },
)

// ── Workflows ─────────────────────────────────────────────────────────────────

export const workflowApi = {
  list: (page = 1, pageSize = 20, status?: string) =>
    api
      .get<PaginatedWorkflows>('/workflows/', {
        params: { page, page_size: pageSize, ...(status ? { status } : {}) },
      })
      .then((r) => r.data),

  get: (id: string) =>
    api.get<WorkflowResponse>(`/workflows/${id}`).then((r) => r.data),

  create: (payload: WorkflowCreate) =>
    api.post<WorkflowResponse>('/workflows/', payload).then((r) => r.data),

  update: (id: string, payload: WorkflowUpdate) =>
    api.patch<WorkflowResponse>(`/workflows/${id}`, payload).then((r) => r.data),

  delete: (id: string) => api.delete(`/workflows/${id}`),
}

// ── Execution Logs ────────────────────────────────────────────────────────────
// The backend does not yet expose a dedicated endpoint — we call the orchestrator
// service directly if available, or fall back to a mock.

export const executionApi = {
  listByWorkflow: (workflowId: string): Promise<ExecutionLogResponse[]> =>
    api
      .get<ExecutionLogResponse[]>(`/workflows/${workflowId}/executions`)
      .then((r) => r.data)
      .catch(() => {
        // Graceful fallback: return empty list when endpoint is not yet available
        console.warn('[executionApi] endpoint not available — using empty fallback')
        return []
      }),

  /** Trigger a workflow execution via the orchestrator service */
  trigger: (workflowId: string, payload?: Record<string, unknown>) =>
    api
      .post(`/workflows/${workflowId}/execute`, payload ?? {})
      .then((r) => r.data)
      .catch((err) => {
        throw err
      }),
}

export default api
