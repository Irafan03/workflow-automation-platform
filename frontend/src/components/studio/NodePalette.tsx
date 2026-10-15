import { Zap, BrainCircuit, Settings2, GitBranch, ArrowDownToLine, Repeat2 } from 'lucide-react'
import type { NodeType } from '@/types'

interface PaletteItem {
  type: NodeType
  label: string
  description: string
  icon: React.ReactNode
  color: string
}

const PALETTE_ITEMS: PaletteItem[] = [
  {
    type: 'trigger',
    label: 'Trigger',
    description: 'Start the workflow',
    icon: <Zap size={14} />,
    color: 'text-amber-400 bg-amber-600/20',
  },
  {
    type: 'agent',
    label: 'Agent',
    description: 'LLM-powered step',
    icon: <BrainCircuit size={14} />,
    color: 'text-brand-500 bg-brand-500/20',
  },
  {
    type: 'action',
    label: 'Action',
    description: 'Execute an action',
    icon: <Settings2 size={14} />,
    color: 'text-violet-400 bg-violet-600/20',
  },
  {
    type: 'condition',
    label: 'Condition',
    description: 'Branch the flow',
    icon: <GitBranch size={14} />,
    color: 'text-orange-400 bg-orange-600/20',
  },
  {
    type: 'transform',
    label: 'Transform',
    description: 'Modify data',
    icon: <Repeat2 size={14} />,
    color: 'text-pink-400 bg-pink-600/20',
  },
  {
    type: 'output',
    label: 'Output',
    description: 'Final output step',
    icon: <ArrowDownToLine size={14} />,
    color: 'text-teal-400 bg-teal-600/20',
  },
]

export function NodePalette() {
  function onDragStart(event: React.DragEvent, nodeType: NodeType) {
    event.dataTransfer.setData('application/reactflow/type', nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <aside
      className="w-52 shrink-0 bg-surface-800 border-r border-white/10 flex flex-col"
      aria-label="Node palette"
    >
      <div className="px-3 py-3 border-b border-white/10">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Nodes
        </p>
        <p className="text-[11px] text-gray-600 mt-0.5">Drag onto canvas</p>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {PALETTE_ITEMS.map((item) => (
          <div
            key={item.type}
            draggable
            onDragStart={(e) => onDragStart(e, item.type)}
            className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg border border-white/5 bg-surface-900
                       hover:border-white/20 hover:bg-white/5 cursor-grab active:cursor-grabbing transition-colors select-none"
            role="button"
            tabIndex={0}
            aria-label={`Add ${item.label} node`}
          >
            <div className={`p-1.5 rounded-md shrink-0 ${item.color}`}>{item.icon}</div>
            <div>
              <p className="text-xs font-medium text-white">{item.label}</p>
              <p className="text-[10px] text-gray-500">{item.description}</p>
            </div>
          </div>
        ))}
      </div>
    </aside>
  )
}
