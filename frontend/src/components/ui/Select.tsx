import clsx from 'clsx'
import type { SelectHTMLAttributes } from 'react'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: { value: string; label: string }[]
}

export function Select({ label, error, options, className, id, ...props }: SelectProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={inputId} className="text-xs font-medium text-gray-400">
          {label}
        </label>
      )}
      <select
        id={inputId}
        {...props}
        className={clsx(
          'bg-surface-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-100',
          'focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50',
          'disabled:opacity-50 disabled:cursor-not-allowed transition-colors appearance-none',
          error && 'border-red-500/60',
          className,
        )}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-surface-800">
            {opt.label}
          </option>
        ))}
      </select>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}
