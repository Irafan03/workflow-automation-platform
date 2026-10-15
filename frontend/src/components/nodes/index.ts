import type { NodeTypes } from 'reactflow'
import { TriggerNode } from './TriggerNode'
import { AgentNode } from './AgentNode'
import { ActionNode } from './ActionNode'
import { ConditionNode, OutputNode, TransformNode } from './OtherNodes'

/** Registered React Flow node types — keys must match NodeType values */
export const nodeTypes: NodeTypes = {
  trigger: TriggerNode,
  agent: AgentNode,
  action: ActionNode,
  condition: ConditionNode,
  output: OutputNode,
  transform: TransformNode,
}
