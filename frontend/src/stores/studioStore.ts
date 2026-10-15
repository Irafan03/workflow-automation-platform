import { create } from 'zustand'
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from 'reactflow'
import type { FlowNodeData, NodeResponse, WorkflowResponse } from '@/types'

interface StudioState {
  nodes: Node<FlowNodeData>[]
  edges: Edge[]
  selectedNode: Node<FlowNodeData> | null
  isDirty: boolean

  // actions
  setNodes: (nodes: Node<FlowNodeData>[]) => void
  setEdges: (edges: Edge[]) => void
  onNodesChange: (changes: NodeChange[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  selectNode: (node: Node<FlowNodeData> | null) => void
  updateNodeData: (nodeId: string, data: Partial<FlowNodeData>) => void
  loadWorkflow: (workflow: WorkflowResponse) => void
  addNode: (node: Node<FlowNodeData>) => void
  removeNode: (nodeId: string) => void
  markClean: () => void
}

/** Convert backend NodeResponse[] → React Flow nodes + edges */
function workflowToFlow(workflow: WorkflowResponse): {
  nodes: Node<FlowNodeData>[]
  edges: Edge[]
} {
  const nodes: Node<FlowNodeData>[] = workflow.nodes.map((n: NodeResponse) => ({
    id: n.id,
    type: n.node_type,
    position: {
      x: n.position_x ?? 200,
      y: n.position_y ?? 200,
    },
    data: {
      label: n.name,
      node_type: n.node_type,
      config: n.config,
      agent_config: n.agent_config,
      backendId: n.id,
    },
  }))

  const edges: Edge[] = []
  workflow.nodes.forEach((n: NodeResponse) => {
    if (n.next_nodes) {
      n.next_nodes.forEach((targetId, idx) => {
        edges.push({
          id: `${n.id}-${targetId}-${idx}`,
          source: n.id,
          target: targetId,
          type: 'smoothstep',
        })
      })
    }
  })

  return { nodes, edges }
}

export const useStudioStore = create<StudioState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  isDirty: false,

  setNodes: (nodes) => set({ nodes, isDirty: true }),
  setEdges: (edges) => set({ edges, isDirty: true }),

  onNodesChange: (changes) => {
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes) as Node<FlowNodeData>[],
      isDirty: true,
    }))
  },

  onEdgesChange: (changes) => {
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
      isDirty: true,
    }))
  },

  onConnect: (connection) => {
    set((state) => ({
      edges: addEdge({ ...connection, type: 'smoothstep' }, state.edges),
      isDirty: true,
    }))
  },

  selectNode: (node) => set({ selectedNode: node }),

  updateNodeData: (nodeId, data) => {
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n,
      ),
      isDirty: true,
    }))
    // Keep selectedNode in sync
    const updated = get().nodes.find((n) => n.id === nodeId)
    if (updated) set({ selectedNode: updated })
  },

  loadWorkflow: (workflow) => {
    const { nodes, edges } = workflowToFlow(workflow)
    set({ nodes, edges, isDirty: false, selectedNode: null })
  },

  addNode: (node) => {
    set((state) => ({ nodes: [...state.nodes, node], isDirty: true }))
  },

  removeNode: (nodeId) => {
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== nodeId),
      edges: state.edges.filter(
        (e) => e.source !== nodeId && e.target !== nodeId,
      ),
      selectedNode: state.selectedNode?.id === nodeId ? null : state.selectedNode,
      isDirty: true,
    }))
  },

  markClean: () => set({ isDirty: false }),
}))
