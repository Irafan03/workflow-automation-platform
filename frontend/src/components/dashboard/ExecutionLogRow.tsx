import { useState } from 'react'
import { ChevronDown, ChevronRight, Clock, Timer } from 'lucide-react'
import { StatusBadge } from '@/components/ui/StatusBadge'
import type { ExecutionLogResponse } from '@/types'
import clsx from 'clsx'

interface ExecutionLogRowProps {
  log: ExecutionLogResponse
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function formatDuration(ms: number | null) {
  if (ms === null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

export function ExecutionLogRow({ log }: ExecutionLogRowProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-white/10 rounded-lg overflow-hidden bg-surface-800">
      {/* Summary row */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 transition-colors text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="text-gray-500 shrink-0">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>

        <StatusBadge status={log.status} />

        <span className="flex-1 text-xs text-gray-400 font-mono truncate">
          {log.id.slice(0, 8)}…
        </span>

        <span className="flex items-center gap-1 text-xs text-gray-500 shrink-0">
          <Clock size={11} />
          {formatDate(log.started_at ?? log.created_at)}
        </span>

        <span className="flex items-center gap-1 text-xs text-gray-500 shrink-0 w-16 justify-end">
          <Timer size={11} />
          {formatDuration(log.duration_ms)}
        </span>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-white/10 px-4 py-3 space-y-3">
          {/* Error message */}
          {log.error_message && (
            <div className="bg-red-900/20 border border-red-700/40 rounded-lg p-3">
              <p className="text-xs font-semibold text-red-400 mb-1">Error</p>
              <p className="text-xs text-red-300 font-mono">{log.error_message}</p>
            </div>
          )}

          {/* Steps */}
          {log.steps && log.steps.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Steps ({log.steps.length})
              </p>
              <div className="space-y-1">
                {log.steps.map((step, idx) => (
                  <div
                    key={idx}
                    className={clsx(
                      'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs',
                      step.status === 'success' && 'bg-emerald-900/20',
                      step.status === 'failed' && 'bg-red-900/20',
                      step.status === 'running' && 'bg-blue-900/20',
                      !['success', 'failed', 'running'].includes(step.status) && 'bg-surface-900',
                    )}
                  >
                    <StatusBadge status={step.status} />
                    <span className="text-gray-300 font-medium">
                      {step.node_name ?? step.node_id.slice(0, 8)}
                    </span>
                    {step.duration_ms !== undefined && (
                      <span className="ml-auto text-gray-500">
                        {formatDuration(step.duration_ms)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Output preview */}
          {log.output && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                Output
              </p>
              <pre className="text-xs text-gray-400 bg-surface-900 p-3 rounded-lg overflow-x-auto max-h-40">
                {JSON.stringify(log.output, null, 2)}
              </pre>
            </div>
          )}

          {/* MLflow run */}
          {log.mlflow_run_id && (
            <p className="text-xs text-gray-600">
              MLflow run: <span className="font-mono text-gray-400">{log.mlflow_run_id}</span>
            </p>
          )}
        </div>
      )}
    </div>
  )
}
