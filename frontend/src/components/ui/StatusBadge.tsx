import clsx from 'clsx'
import type { ExecutionStatus, WorkflowStatus } from '@/types'

type Status = WorkflowStatus | ExecutionStatus

const colorMap: Record<Status, string> = {
  // WorkflowStatus
  draft: 'bg-gray-700 text-gray-300',
  active: 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50',
  paused: 'bg-yellow-900/60 text-yellow-300 border border-yellow-700/50',
  archived: 'bg-gray-800 text-gray-500',
  // ExecutionStatus
  pending: 'bg-gray-700 text-gray-300',
  running: 'bg-blue-900/60 text-blue-300 border border-blue-700/50 animate-pulse',
  success: 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50',
  failed: 'bg-red-900/60 text-red-300 border border-red-700/50',
  cancelled: 'bg-gray-700 text-gray-400',
}

interface BadgeProps {
  status: Status
  className?: string
}

export function StatusBadge({ status, className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        colorMap[status],
        className,
      )}
    >
      {status}
    </span>
  )
}
