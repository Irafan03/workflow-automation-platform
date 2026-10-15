import { Settings } from 'lucide-react'

export function SettingsPage() {
  return (
    <div className="flex flex-col h-full bg-surface-900">
      <header className="border-b border-white/10 px-6 py-4 flex items-center gap-2">
        <Settings size={18} className="text-brand-500" />
        <h1 className="text-base font-semibold text-white">Settings</h1>
      </header>
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-500 text-sm">Settings coming soon.</p>
      </div>
    </div>
  )
}
