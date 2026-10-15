import { useState, useEffect } from 'react'
import { X, Trash2 } from 'lucide-react'
import type { Node } from 'reactflow'
import { useStudioStore } from '@/stores/studioStore'
import type { FlowNodeData, AgentConfigResponse } from '@/types'
import { Input, Textarea } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'

const MODEL_PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'mistral', label: 'Mistral AI' },
  { value: 'ollama', label: 'Ollama (local)' },
]

const MODELS_BY_PROVIDER: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
  ],
  anthropic: [
    { value: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
    { value: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku' },
    { value: 'claude-3-opus-20240229', label: 'Claude 3 Opus' },
  ],
  mistral: [
    { value: 'mistral-large-latest', label: 'Mistral Large' },
    { value: 'mistral-small-latest', label: 'Mistral Small' },
  ],
  ollama: [
    { value: 'llama3.2', label: 'Llama 3.2' },
    { value: 'qwen2.5', label: 'Qwen 2.5' },
    { value: 'deepseek-r1', label: 'DeepSeek R1' },
  ],
}

interface ConfigPanelProps {
  node: Node<FlowNodeData>
  onClose: () => void
}

export function ConfigPanel({ node, onClose }: ConfigPanelProps) {
  const { updateNodeData, removeNode } = useStudioStore()

  // Local state mirrors node data for controlled inputs
  const [label, setLabel] = useState(node.data.label)
  const [agentConfig, setAgentConfig] = useState<Partial<AgentConfigResponse>>(
    node.data.agent_config ?? {
      model_provider: 'openai',
      model_name: 'gpt-4o',
      temperature: 0.7,
      max_tokens: 1024,
      system_prompt: '',
    },
  )

  // Sync when selected node changes
  useEffect(() => {
    setLabel(node.data.label)
    setAgentConfig(
      node.data.agent_config ?? {
        model_provider: 'openai',
        model_name: 'gpt-4o',
        temperature: 0.7,
        max_tokens: 1024,
        system_prompt: '',
      },
    )
  }, [node.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const isAgent = node.data.node_type === 'agent'

  function handleSave() {
    updateNodeData(node.id, {
      label,
      ...(isAgent ? { agent_config: agentConfig as AgentConfigResponse } : {}),
    })
  }

  function handleDelete() {
    removeNode(node.id)
    onClose()
  }

  const availableModels =
    MODELS_BY_PROVIDER[agentConfig.model_provider ?? 'openai'] ?? []

  return (
    <aside
      className="w-80 shrink-0 bg-surface-800 border-l border-white/10 flex flex-col h-full"
      aria-label="Node configuration panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
        <div>
          <h3 className="text-sm font-semibold text-white capitalize">
            {node.data.node_type} node
          </h3>
          <p className="text-xs text-gray-500 font-mono truncate max-w-[180px]">
            {node.id}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-white p-1 rounded transition-colors"
          aria-label="Close panel"
        >
          <X size={16} />
        </button>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
        {/* Common: node label */}
        <Input
          label="Node name"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="My node"
        />

        {/* Agent-specific configuration */}
        {isAgent && (
          <>
            <hr className="border-white/10" />
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Agent configuration
            </p>

            <Select
              label="Model provider"
              value={agentConfig.model_provider ?? 'openai'}
              onChange={(e) =>
                setAgentConfig((prev) => ({
                  ...prev,
                  model_provider: e.target.value,
                  model_name: MODELS_BY_PROVIDER[e.target.value]?.[0]?.value ?? '',
                }))
              }
              options={MODEL_PROVIDERS}
            />

            <Select
              label="Model"
              value={agentConfig.model_name ?? ''}
              onChange={(e) =>
                setAgentConfig((prev) => ({ ...prev, model_name: e.target.value }))
              }
              options={
                availableModels.length
                  ? availableModels
                  : [{ value: agentConfig.model_name ?? '', label: agentConfig.model_name ?? 'Custom' }]
              }
            />

            <Input
              label="Model version (optional)"
              value={agentConfig.model_version ?? ''}
              onChange={(e) =>
                setAgentConfig((prev) => ({ ...prev, model_version: e.target.value || null }))
              }
              placeholder="e.g. 2024-07-01"
            />

            <Textarea
              label="System prompt"
              value={agentConfig.system_prompt ?? ''}
              onChange={(e) =>
                setAgentConfig((prev) => ({ ...prev, system_prompt: e.target.value }))
              }
              rows={6}
              placeholder="You are a helpful assistant..."
            />

            {/* Temperature slider */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-gray-400">Temperature</label>
                <span className="text-xs font-mono text-brand-500">
                  {agentConfig.temperature?.toFixed(2) ?? '0.70'}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={2}
                step={0.01}
                value={agentConfig.temperature ?? 0.7}
                onChange={(e) =>
                  setAgentConfig((prev) => ({
                    ...prev,
                    temperature: parseFloat(e.target.value),
                  }))
                }
                className="w-full accent-brand-500"
                aria-label="Temperature"
              />
              <div className="flex justify-between text-[10px] text-gray-600">
                <span>Precise (0)</span>
                <span>Creative (2)</span>
              </div>
            </div>

            <Input
              label="Max tokens"
              type="number"
              min={1}
              max={128000}
              value={agentConfig.max_tokens ?? 1024}
              onChange={(e) =>
                setAgentConfig((prev) => ({
                  ...prev,
                  max_tokens: parseInt(e.target.value, 10),
                }))
              }
            />

            <Input
              label="MLflow Experiment ID (optional)"
              value={agentConfig.mlflow_experiment_id ?? ''}
              onChange={(e) =>
                setAgentConfig((prev) => ({
                  ...prev,
                  mlflow_experiment_id: e.target.value || null,
                }))
              }
              placeholder="experiment-001"
            />
          </>
        )}

        {/* Generic config for non-agent nodes */}
        {!isAgent && node.data.config && (
          <>
            <hr className="border-white/10" />
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Configuration (JSON)
            </p>
            <pre className="text-xs text-gray-400 bg-surface-900 p-3 rounded-lg overflow-x-auto">
              {JSON.stringify(node.data.config, null, 2)}
            </pre>
          </>
        )}
      </div>

      {/* Footer actions */}
      <div className="px-4 py-3 border-t border-white/10 flex items-center justify-between gap-2">
        <Button
          variant="danger"
          size="sm"
          icon={<Trash2 size={13} />}
          onClick={handleDelete}
        >
          Delete
        </Button>
        <Button variant="primary" size="sm" onClick={handleSave}>
          Apply
        </Button>
      </div>
    </aside>
  )
}
