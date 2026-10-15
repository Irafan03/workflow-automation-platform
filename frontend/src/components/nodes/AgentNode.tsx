import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import { BrainCircuit } from 'lucide-react'
import clsx from 'clsx'
import type { FlowNodeData } from '@/types'

export const AgentNode = memo(({ data, selected }: NodeProps<FlowNodeData>) => {
  const ac = data.agent_config
  return (
    <div
      className={clsx(
        'min-w-[180px] rounded-xl border-2 bg-surface-800 shadow-lg transition-all',
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
      <div className="flex items-center gap-2 px-3 py-2 bg-brand-500/20 rounded-t-[10px] border-b border-white/10">
        <div className="p-1 bg-brand-500/20 rounded-md">
          <BrainCircuit size={12} className="text-brand-500" />
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-brand-500">
          Agent
        </span>
      </div>

      {/* Body */}
      <div className="px-3 py-2.5 space-y-1">
        <p className="text-sm font-medium text-white truncate max-w-[180px]">
          {data.label}
        </p>
        {ac ? (
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-gray-400 font-mono truncate">
              {ac.model_provider}/{ac.model_name}
            </span>
            <span className="text-xs text-gray-600">
              temp={ac.temperature} · max={ac.max_tokens}
            </span>
          </div>
        ) : (
          <p className="text-xs text-gray-600 italic">No model configured</p>
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

AgentNode.displayName = 'AgentNode'
