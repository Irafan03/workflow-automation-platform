import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { Zap } from 'lucide-react'
import clsx from 'clsx'
import type { FlowNodeData } from '@/types'

export const TriggerNode = memo(({ data, selected }: NodeProps<FlowNodeData>) => {
  return (
    <div
      className={clsx(
        'min-w-[160px] rounded-xl border-2 bg-surface-800 shadow-lg transition-all',
        selected
          ? 'border-brand-500 shadow-brand-500/20 shadow-xl'
          : 'border-white/10 hover:border-white/30',
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-amber-600/20 rounded-t-[10px] border-b border-white/10">
        <div className="p-1 bg-amber-500/20 rounded-md">
          <Zap size={12} className="text-amber-400" />
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">
          Trigger
        </span>
      </div>

      {/* Body */}
      <div className="px-3 py-2.5">
        <p className="text-sm font-medium text-white truncate max-w-[160px]">
          {data.label}
        </p>
        {data.config?.type != null && (
          <p className="text-xs text-gray-500 mt-0.5">{String(data.config.type)}</p>
        )}
      </div>

      {/* Only output handle — triggers have no input */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3"
        aria-label="Output handle"
      />
    </div>
  )
})

TriggerNode.displayName = 'TriggerNode'
