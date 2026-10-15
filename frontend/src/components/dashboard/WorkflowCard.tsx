import { useNavigate } from 'react-router-dom'
import { Pencil, Trash2, Play, Clock } from 'lucide-react'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Button } from '@/components/ui/Button'
import { useWorkflowStore } from '@/stores/workflowStore'
import { executionApi } from '@/api/client'
import type { WorkflowSummary } from '@/types'

interface WorkflowCardProps {
  workflow: WorkflowSummary
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function WorkflowCard({ workflow }: WorkflowCardProps) {
  const navigate = useNavigate()
  const { deleteWorkflow } = useWorkflowStore()

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm(`Delete "${workflow.name}"? This cannot be undone.`)) return
    await deleteWorkflow(workflow.id)
  }

  async function handleRun(e: React.MouseEvent) {
    e.stopPropagation()
    try {
      await executionApi.trigger(workflow.id, {})
    } catch (err) {
      console.error('Trigger failed:', err)
    }
  }

  return (
    <article
      className="group relative bg-surface-800 border border-white/10 rounded-xl p-4
                 hover:border-brand-500/40 hover:shadow-brand-500/10 hover:shadow-lg
                 transition-all cursor-pointer"
      onClick={() => navigate(`/studio/${workflow.id}`)}
      aria-label={`Open workflow ${workflow.name}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-white truncate">{workflow.name}</h3>
          {workflow.description && (
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{workflow.description}</p>
          )}
        </div>
        <StatusBadge status={workflow.status} className="shrink-0 mt-0.5" />
      </div>

      <div className="flex items-center justify-between mt-3">
        <span className="flex items-center gap-1.5 text-[11px] text-gray-600">
          <Clock size={11} />
          {formatDate(workflow.updated_at)}
        </span>

        {/* Action buttons — visible on hover */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <Button
            variant="ghost"
            size="sm"
            icon={<Pencil size={12} />}
            onClick={(e) => { e.stopPropagation(); navigate(`/studio/${workflow.id}`) }}
            aria-label="Edit workflow"
          />
          <Button
            variant="ghost"
            size="sm"
            icon={<Play size={12} />}
            onClick={handleRun}
            aria-label="Run workflow"
          />
          <Button
            variant="ghost"
            size="sm"
            icon={<Trash2 size={12} />}
            onClick={handleDelete}
            className="hover:text-red-400"
            aria-label="Delete workflow"
          />
        </div>
      </div>
    </article>
  )
}
