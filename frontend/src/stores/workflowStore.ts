import { create } from 'zustand'
import { workflowApi } from '@/api/client'
import type {
  WorkflowCreate,
  WorkflowResponse,
  WorkflowSummary,
  WorkflowUpdate,
} from '@/types'

interface WorkflowState {
  // list
  workflows: WorkflowSummary[]
  total: number
  page: number
  pageSize: number
  statusFilter: string | undefined
  listLoading: boolean
  listError: string | null

  // current detail
  current: WorkflowResponse | null
  detailLoading: boolean
  detailError: string | null

  // actions
  fetchList: (page?: number, status?: string) => Promise<void>
  fetchOne: (id: string) => Promise<void>
  createWorkflow: (payload: WorkflowCreate) => Promise<WorkflowResponse>
  updateWorkflow: (id: string, payload: WorkflowUpdate) => Promise<WorkflowResponse>
  deleteWorkflow: (id: string) => Promise<void>
  clearCurrent: () => void
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  workflows: [],
  total: 0,
  page: 1,
  pageSize: 20,
  statusFilter: undefined,
  listLoading: false,
  listError: null,

  current: null,
  detailLoading: false,
  detailError: null,

  fetchList: async (page = 1, status?: string) => {
    set({ listLoading: true, listError: null, page, statusFilter: status })
    try {
      const data = await workflowApi.list(page, get().pageSize, status)
      set({ workflows: data.items, total: data.total, listLoading: false })
    } catch (err) {
      set({ listError: (err as Error).message, listLoading: false })
    }
  },

  fetchOne: async (id: string) => {
    set({ detailLoading: true, detailError: null })
    try {
      const data = await workflowApi.get(id)
      set({ current: data, detailLoading: false })
    } catch (err) {
      set({ detailError: (err as Error).message, detailLoading: false })
    }
  },

  createWorkflow: async (payload: WorkflowCreate) => {
    const data = await workflowApi.create(payload)
    // Refresh list after creation
    await get().fetchList(1, get().statusFilter)
    return data
  },

  updateWorkflow: async (id: string, payload: WorkflowUpdate) => {
    const data = await workflowApi.update(id, payload)
    set({ current: data })
    // Refresh list in background
    get().fetchList(get().page, get().statusFilter)
    return data
  },

  deleteWorkflow: async (id: string) => {
    await workflowApi.delete(id)
    set((state) => ({
      workflows: state.workflows.filter((w) => w.id !== id),
      total: state.total - 1,
    }))
  },

  clearCurrent: () => set({ current: null, detailError: null }),
}))
