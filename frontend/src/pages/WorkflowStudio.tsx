import { useCallback, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  type Node,
  type ReactFlowInstance,
} from 'reactflow'
import 'reactflow/dist/style.css'

import { useWorkflowStore } from '@/stores/workflowStore'
import { useStudioStore } from '@/stores/studioStore'
import { nodeTypes } from '@/components/nodes'
import { NodePalette } from '@/components/studio/NodePalette'
import { ConfigPanel } from '@/components/studio/ConfigPanel'
import { StudioToolbar } from '@/components/studio/StudioToolbar'
import type { FlowNodeData, NodeType } from '@/types'

let nodeCounter = 1

export function WorkflowStudio() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const rfInstanceRef = useRef<ReactFlowInstance | null>(null)

  const { current, detailLoading, detailError, fetchOne } = useWorkflowStore()
  const {
    nodes,
    edges,
    selectedNode,
    onNodesChange,
    onEdgesChange,
    onConnect,
    selectNode,
    loadWorkflow,
    addNode,
  } = useStudioStore()

  // Load workflow on mount
  useEffect(() => {
    if (id) fetchOne(id)
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Populate canvas when workflow data arrives
  useEffect(() => {
    if (current && current.id === id) {
      loadWorkflow(current)
    }
  }, [current, id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Handle dropping a new node from the palette
  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault()
      const nodeType = event.dataTransfer.getData('application/reactflow/type') as NodeType
      if (!nodeType || !rfInstanceRef.current) return

      const position = rfInstanceRef.current.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      })

      const newNode: Node<FlowNodeData> = {
        id: `new-${nodeType}-${nodeCounter++}`,
        type: nodeType,
        position,
        data: {
          label: `${nodeType.charAt(0).toUpperCase() + nodeType.slice(1)} ${nodeCounter - 1}`,
          node_type: nodeType,
          config: null,
          agent_config: nodeType === 'agent'
            ? {
                id: '',
                node_id: '',
                model_provider: 'openai',
                model_name: 'gpt-4o',
                model_version: null,
                system_prompt: '',
                temperature: 0.7,
                max_tokens: 1024,
                tools: null,
                mlflow_experiment_id: null,
                created_at: '',
                updated_at: '',
              }
            : undefined,
        },
      }
      addNode(newNode)
      selectNode(newNode)
    },
    [addNode, selectNode],
  )

  const onDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node<FlowNodeData>) => {
      selectNode(node)
    },
    [selectNode],
  )

  const onPaneClick = useCallback(() => {
    selectNode(null)
  }, [selectNode])

  if (detailLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-surface-900">
        <div className="text-gray-500 text-sm animate-pulse">Loading workflow…</div>
      </div>
    )
  }

  if (detailError || !current) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 bg-surface-900">
        <p className="text-red-400 text-sm">{detailError ?? 'Workflow not found'}</p>
        <button
          onClick={() => navigate('/')}
          className="text-brand-500 underline text-sm"
        >
          Back to dashboard
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-surface-900 overflow-hidden">
      <StudioToolbar workflow={current} />

      <div className="flex flex-1 overflow-hidden">
        {/* Node palette */}
        <NodePalette />

        {/* React Flow canvas */}
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onInit={(instance) => { rfInstanceRef.current = instance }}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.15 }}
            deleteKeyCode="Delete"
            multiSelectionKeyCode="Shift"
            className="bg-surface-900"
            defaultEdgeOptions={{ type: 'smoothstep', animated: true }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={24}
              size={1}
              color="#1c1f2e"
            />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const type = (n.data as FlowNodeData)?.node_type
                const map: Record<string, string> = {
                  trigger: '#f59e0b',
                  agent: '#4f6ef7',
                  action: '#8b5cf6',
                  condition: '#f97316',
                  transform: '#ec4899',
                  output: '#14b8a6',
                }
                return map[type] ?? '#374151'
              }}
              maskColor="rgba(19,21,31,0.7)"
            />
          </ReactFlow>
        </div>

        {/* Config panel — only shown when a node is selected */}
        {selectedNode && (
          <ConfigPanel node={selectedNode} onClose={() => selectNode(null)} />
        )}
      </div>
    </div>
  )
}
