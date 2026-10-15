import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { GitBranch, ArrowDownToLine, Repeat2 } from 'lucide-react'
import clsx from 'clsx'
import type { FlowNodeData } from '@/types'

// ── Condition ─────────────────────────────────────────────────────────────────

export const ConditionNode = memo(({ data, selected }: NodeProps<FlowNodeData>) => (
  <div
    className={clsx(
      'min-w-[160px] rounded-xl border-2 bg-surface-800 shadow-lg transition-all',
      selected
        ? 'border-brand-500 shadow-brand-500/20 shadow-xl'
        : 'border-white/10 hover:border-white/30',
    )}
  >
    <Handle type="target" position={Position.Top} className="!w-3 !h-3" />
    <div className="flex items-center gap-2 px-3 py-2 bg-orange-600/20 rounded-t-[10px] border-b border-white/10">
      <GitBranch size={12} className="text-orange-400" />
      <span className="text-[10px] font-semibold uppercase tracking-wider text-orange-400">
        Condition
      </span>
    </div>
    <div className="px-3 py-2.5">
      <p className="text-sm font-medium text-white truncate max-w-[160px]">{data.label}</p>
    </div>
    <Handle type="source" position={Position.Bottom} className="!w-3 !h-3" />
  </div>
))
ConditionNode.displayName = 'ConditionNode'

// ── Output ────────────────────────────────────────────────────────────────────

export const OutputNode = memo(({ data, selected }: NodeProps<FlowNodeData>) => (
  <div
    className={clsx(
      'min-w-[160px] rounded-xl border-2 bg-surface-800 shadow-lg transition-all',
      selected
        ? 'border-brand-500 shadow-brand-500/20 shadow-xl'
        : 'border-white/10 hover:border-white/30',
    )}
  >
    <Handle type="target" position={Position.Top} className="!w-3 !h-3" />
    <div className="flex items-center gap-2 px-3 py-2 bg-teal-600/20 rounded-t-[10px] border-b border-white/10">
      <ArrowDownToLine size={12} className="text-teal-400" />
      <span className="text-[10px] font-semibold uppercase tracking-wider text-teal-400">
        Output
      </span>
    </div>
    <div className="px-3 py-2.5">
      <p className="text-sm font-medium text-white truncate max-w-[160px]">{data.label}</p>
    </div>
  </div>
))
OutputNode.displayName = 'OutputNode'

// ── Transform ─────────────────────────────────────────────────────────────────

export const TransformNode = memo(({ data, selected }: NodeProps<FlowNodeData>) => (
  <div
    className={clsx(
      'min-w-[160px] rounded-xl border-2 bg-surface-800 shadow-lg transition-all',
      selected
        ? 'border-brand-500 shadow-brand-500/20 shadow-xl'
        : 'border-white/10 hover:border-white/30',
    )}
  >
    <Handle type="target" position={Position.Top} className="!w-3 !h-3" />
    <div className="flex items-center gap-2 px-3 py-2 bg-pink-600/20 rounded-t-[10px] border-b border-white/10">
      <Repeat2 size={12} className="text-pink-400" />
      <span className="text-[10px] font-semibold uppercase tracking-wider text-pink-400">
        Transform
      </span>
    </div>
    <div className="px-3 py-2.5">
      <p className="text-sm font-medium text-white truncate max-w-[160px]">{data.label}</p>
    </div>
    <Handle type="source" position={Position.Bottom} className="!w-3 !h-3" />
  </div>
))
TransformNode.displayName = 'TransformNode'
