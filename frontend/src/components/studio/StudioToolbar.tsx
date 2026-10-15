import { useState } from 'react'
import { ArrowLeft, Save, Play, MoreHorizontal } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import { useStudioStore } from '@/stores/studioStore'
import { useWorkflowStore } from '@/stores/workflowStore'
import { executionApi } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/StatusBadge'
import type { WorkflowResponse } from '@/types'

interface StudioToolbarProps {
  workflow: WorkflowResponse
}

export function StudioToolbar({ workflow }: StudioToolbarProps) {
  const navigate = useNavigate()
  const { nodes, edges, isDirty, markClean } = useStudioStore()
  const { updateWorkflow } = useWorkflowStore()
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  async function handleSave() {
    setSaving(true)
    setSaveError(null)
    try {
      // Build the updated nodes payload from the canvas
      const updatedNodes = nodes.map((n) => ({
        name: n.data.label,
        node_type: n.data.node_type,
        position_x: n.position.x,
        position_y: n.position.y,
        config: n.data.config ?? null,
        next_nodes: edges
          .filter((e) => e.source === n.id)
          .map((e) => e.target),
        order: 0,
        agent_config: n.data.agent_config
          ? {
              model_provider: n.data.agent_config.model_provider,
              model_name: n.data.agent_config.model_name,
              model_version: n.data.agent_config.model_version ?? undefined,
              system_prompt: n.data.agent_config.system_prompt ?? undefined,
              temperature: n.data.agent_config.temperature,
              max_tokens: n.data.agent_config.max_tokens,
              tools: n.data.agent_config.tools ?? undefined,
              mlflow_experiment_id: n.data.agent_config.mlflow_experiment_id ?? undefined,
            }
          : null,
      }))

      // PATCH workflow metadata — nodes are replaced via a full PUT-style create
      // For now we patch the meta field to store the full graph as JSON backup
      await updateWorkflow(workflow.id, {
        meta: {
          ...workflow.meta,
          canvas_snapshot: { nodes: updatedNodes, edge_count: edges.length },
        },
      })

      markClean()
    } catch (err) {
      setSaveError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function handleRun() {
    setRunning(true)
    try {
      await executionApi.trigger(workflow.id, {})
      // TODO: navigate to execution log or show toast
    } catch (err) {
      console.error('Run failed:', err)
    } finally {
      setRunning(false)
    }
  }

  return (
    <header className="h-12 bg-surface-800 border-b border-white/10 flex items-center px-3 gap-3 shrink-0">
      {/* Back */}
      <button
        onClick={() => navigate('/')}
        className="text-gray-500 hover:text-white p-1.5 rounded transition-colors"
        aria-label="Back to dashboard"
      >
        <ArrowLeft size={16} />
      </button>

      <div className="w-px h-5 bg-white/10" />

      {/* Workflow info */}
      <div className="flex items-center gap-2 min-w-0">
        <h1 className="text-sm font-semibold text-white truncate max-w-xs">
          {workflow.name}
        </h1>
        <StatusBadge status={workflow.status} />
        {isDirty && (
          <span className="text-[10px] text-amber-400 bg-amber-900/40 px-1.5 py-0.5 rounded">
            unsaved
          </span>
        )}
      </div>

      <div className="flex-1" />

      {/* Error */}
      {saveError && (
        <span className="text-xs text-red-400">{saveError}</span>
      )}

      {/* Stats */}
      <span
        className={clsx(
          'text-xs px-2 py-0.5 rounded bg-surface-900 border border-white/10',
          'text-gray-400 font-mono',
        )}
      >
        {nodes.length} nodes · {edges.length} edges
      </span>

      <Button
        variant="secondary"
        size="sm"
        icon={<Save size={13} />}
        loading={saving}
        onClick={handleSave}
        disabled={!isDirty && !saving}
      >
        Save
      </Button>

      <Button
        variant="primary"
        size="sm"
        icon={<Play size={13} />}
        loading={running}
        onClick={handleRun}
      >
        Run
      </Button>

      <button
        className="text-gray-500 hover:text-white p-1.5 rounded transition-colors"
        aria-label="More options"
      >
        <MoreHorizontal size={16} />
      </button>
    </header>
  )
}
