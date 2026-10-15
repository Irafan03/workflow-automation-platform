import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '@/components/ui/Modal'
import { Input, Textarea } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'
import { useWorkflowStore } from '@/stores/workflowStore'
import type { WorkflowStatus } from '@/types'

interface CreateWorkflowModalProps {
  open: boolean
  onClose: () => void
}

const STATUS_OPTIONS: { value: WorkflowStatus; label: string }[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
]

export function CreateWorkflowModal({ open, onClose }: CreateWorkflowModalProps) {
  const navigate = useNavigate()
  const { createWorkflow } = useWorkflowStore()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState<WorkflowStatus>('draft')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function reset() {
    setName('')
    setDescription('')
    setStatus('draft')
    setError(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const workflow = await createWorkflow({
        name: name.trim(),
        description: description.trim() || null,
        status,
        is_active: status === 'active',
        nodes: [],
      })
      reset()
      onClose()
      navigate(`/studio/${workflow.id}`)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => { reset(); onClose() }}
      title="New workflow"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My automation workflow"
          autoFocus
          required
        />
        <Textarea
          label="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What does this workflow do?"
          rows={3}
        />
        <Select
          label="Initial status"
          value={status}
          onChange={(e) => setStatus(e.target.value as WorkflowStatus)}
          options={STATUS_OPTIONS}
        />
        {error && <p className="text-sm text-red-400">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" onClick={() => { reset(); onClose() }}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={loading}>
            Create &amp; open studio
          </Button>
        </div>
      </form>
    </Modal>
  )
}
