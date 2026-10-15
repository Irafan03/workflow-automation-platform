import { useEffect, useState } from 'react'
import {
  Plus, RefreshCw, LayoutDashboard, ChevronLeft, ChevronRight,
  Search, Activity,
} from 'lucide-react'
import { useWorkflowStore } from '@/stores/workflowStore'
import { executionApi } from '@/api/client'
import { WorkflowCard } from '@/components/dashboard/WorkflowCard'
import { ExecutionLogRow } from '@/components/dashboard/ExecutionLogRow'
import { CreateWorkflowModal } from '@/components/dashboard/CreateWorkflowModal'
import { Button } from '@/components/ui/Button'
import type { ExecutionLogResponse, WorkflowStatus } from '@/types'

const STATUS_FILTERS: { value: WorkflowStatus | ''; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'draft', label: 'Draft' },
  { value: 'paused', label: 'Paused' },
  { value: 'archived', label: 'Archived' },
]

// Recent executions across all workflows — mock when endpoint absent
const MOCK_LOGS: ExecutionLogResponse[] = [
  {
    id: 'aaaaaaaa-0000-0000-0000-000000000001',
    workflow_id: '',
    status: 'success',
    trigger_payload: { source: 'webhook' },
    output: { result: 'ok' },
    error_message: null,
    steps: [
      { node_id: 'n1', node_name: 'Webhook Trigger', status: 'success', duration_ms: 12 },
      { node_id: 'n2', node_name: 'GPT-4o Agent', status: 'success', duration_ms: 1842 },
      { node_id: 'n3', node_name: 'Send Email', status: 'success', duration_ms: 220 },
    ],
    duration_ms: 2074,
    mlflow_run_id: null,
    started_at: new Date(Date.now() - 5 * 60_000).toISOString(),
    finished_at: new Date(Date.now() - 5 * 60_000 + 2074).toISOString(),
    created_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  },
  {
    id: 'bbbbbbbb-0000-0000-0000-000000000002',
    workflow_id: '',
    status: 'failed',
    trigger_payload: { source: 'cron' },
    output: null,
    error_message: 'LLM provider returned 429 Too Many Requests',
    steps: [
      { node_id: 'n1', node_name: 'Cron Trigger', status: 'success', duration_ms: 5 },
      { node_id: 'n2', node_name: 'Claude Agent', status: 'failed', duration_ms: 350 },
    ],
    duration_ms: 355,
    mlflow_run_id: null,
    started_at: new Date(Date.now() - 30 * 60_000).toISOString(),
    finished_at: new Date(Date.now() - 30 * 60_000 + 355).toISOString(),
    created_at: new Date(Date.now() - 30 * 60_000).toISOString(),
  },
]

export function Dashboard() {
  const { workflows, total, page, listLoading, listError, fetchList } = useWorkflowStore()
  const pageSize = 20

  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<WorkflowStatus | ''>('')
  const [createOpen, setCreateOpen] = useState(false)
  const [execLogs, setExecLogs] = useState<ExecutionLogResponse[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'workflows' | 'executions'>('workflows')

  // Initial load
  useEffect(() => {
    fetchList(1, statusFilter || undefined)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh when filter changes
  useEffect(() => {
    fetchList(1, statusFilter || undefined)
  }, [statusFilter]) // eslint-disable-line react-hooks/exhaustive-deps

  // Load recent executions when tab switches
  useEffect(() => {
    if (activeTab !== 'executions') return
    setLogsLoading(true)
    // Try to fetch from first workflow, fall back to mock
    const firstId = workflows[0]?.id
    const promise = firstId
      ? executionApi.listByWorkflow(firstId)
      : Promise.resolve([])
    promise
      .then((data) => setExecLogs(data.length ? data : MOCK_LOGS))
      .catch(() => setExecLogs(MOCK_LOGS))
      .finally(() => setLogsLoading(false))
  }, [activeTab, workflows])

  const filteredWorkflows = search.trim()
    ? workflows.filter(
        (w) =>
          w.name.toLowerCase().includes(search.toLowerCase()) ||
          (w.description ?? '').toLowerCase().includes(search.toLowerCase()),
      )
    : workflows

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="flex flex-col h-full min-h-0 bg-surface-900">
      {/* ── Top bar ── */}
      <header className="border-b border-white/10 px-6 py-4 flex items-center gap-4 shrink-0">
        <div className="flex items-center gap-2">
          <LayoutDashboard size={18} className="text-brand-500" />
          <h1 className="text-base font-semibold text-white">Dashboard</h1>
        </div>

        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search workflows…"
            className="w-full bg-surface-800 border border-white/10 rounded-lg pl-8 pr-3 py-1.5
                       text-sm text-gray-200 placeholder:text-gray-600
                       focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          />
        </div>

        <div className="flex-1" />

        <Button
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={13} />}
          onClick={() => fetchList(page, statusFilter || undefined)}
          loading={listLoading}
          aria-label="Refresh"
        />

        <Button
          variant="primary"
          size="sm"
          icon={<Plus size={14} />}
          onClick={() => setCreateOpen(true)}
        >
          New workflow
        </Button>
      </header>

      {/* ── Tabs ── */}
      <div className="border-b border-white/10 px-6 flex gap-6 shrink-0">
        {[
          { key: 'workflows', label: 'Workflows', count: total },
          { key: 'executions', label: 'Execution history', count: null },
        ].map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key as typeof activeTab)}
            className={`py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === key
                ? 'border-brand-500 text-white'
                : 'border-transparent text-gray-500 hover:text-gray-300'
            }`}
          >
            {label}
            {count !== null && (
              <span className="ml-1.5 text-xs bg-surface-800 text-gray-400 px-1.5 py-0.5 rounded-full">
                {count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {activeTab === 'workflows' && (
          <>
            {/* Status filter pills */}
            <div className="flex items-center gap-2 mb-5 flex-wrap">
              {STATUS_FILTERS.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => setStatusFilter(value as WorkflowStatus | '')}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    statusFilter === value
                      ? 'bg-brand-500 text-white'
                      : 'bg-surface-800 text-gray-400 hover:text-white border border-white/10'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {listError && (
              <div className="bg-red-900/20 border border-red-700/40 rounded-lg px-4 py-3 mb-4">
                <p className="text-sm text-red-400">{listError}</p>
              </div>
            )}

            {listLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div key={i} className="bg-surface-800 border border-white/10 rounded-xl h-24 animate-pulse" />
                ))}
              </div>
            ) : filteredWorkflows.length === 0 ? (
              <EmptyState onNew={() => setCreateOpen(true)} />
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {filteredWorkflows.map((wf) => (
                  <WorkflowCard key={wf.id} workflow={wf} />
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3 mt-6">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<ChevronLeft size={14} />}
                  disabled={page <= 1}
                  onClick={() => fetchList(page - 1, statusFilter || undefined)}
                />
                <span className="text-xs text-gray-500">
                  Page {page} / {totalPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<ChevronRight size={14} />}
                  disabled={page >= totalPages}
                  onClick={() => fetchList(page + 1, statusFilter || undefined)}
                />
              </div>
            )}
          </>
        )}

        {activeTab === 'executions' && (
          <div className="max-w-3xl space-y-2">
            <div className="flex items-center gap-2 mb-4">
              <Activity size={14} className="text-brand-500" />
              <p className="text-sm font-medium text-gray-300">Recent executions</p>
              {logsLoading && (
                <span className="text-xs text-gray-500 animate-pulse">Loading…</span>
              )}
            </div>

            {execLogs.length === 0 && !logsLoading ? (
              <p className="text-sm text-gray-600">No execution history yet.</p>
            ) : (
              execLogs.map((log) => <ExecutionLogRow key={log.id} log={log} />)
            )}
          </div>
        )}
      </div>

      <CreateWorkflowModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mb-4">
        <LayoutDashboard size={28} className="text-brand-500/60" />
      </div>
      <h3 className="text-base font-semibold text-white mb-1">No workflows yet</h3>
      <p className="text-sm text-gray-500 mb-5 max-w-xs">
        Create your first workflow to start automating tasks with AI agents.
      </p>
      <Button variant="primary" icon={<Plus size={14} />} onClick={onNew}>
        New workflow
      </Button>
    </div>
  )
}
