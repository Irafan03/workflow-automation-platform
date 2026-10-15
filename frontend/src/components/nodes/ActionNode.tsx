import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { Settings2 } from 'lucide-react'
import clsx from 'clsx'
import type { FlowNodeData } from '@/types'

export const ActionNode = memo(({ data, selected }: NodeProps<FlowNodeData>) => {
  return (
    <div
      className={clsx(
        'min-w-[160px] rounded-xl border-2 bg-surface-800 shadow-lg transition-all',
        selected
          ? 'border-brand-500 shadow-brand-500/20 shadow-xl'
          : 'border-white/10 hover:border-white/30',
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3"
        aria-label="Input handle"
      />

      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-violet-600/20 rounded-t-[10px] border-b border-white/10">
        <div className="p-1 bg-violet-500/20 rounded-md">
          <Settings2 size={12} className="text-violet-400" />
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-violet-400">
          Action
        </span>
      </div>

      {/* Body */}
      <div className="px-3 py-2.5">
        <p className="text-sm font-medium text-white truncate max-w-[160px]">
          {data.label}
        </p>
        {data.config?.action_type != null && (
          <p className="text-xs text-gray-500 mt-0.5">
            {String(data.config.action_type)}
          </p>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3"
        aria-label="Output handle"
      />
    </div>
  )
})

ActionNode.displayName = 'ActionNode'
