import clsx from 'clsx'
import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export function Input({ label, error, className, id, ...props }: InputProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={inputId} className="text-xs font-medium text-gray-400">
          {label}
        </label>
      )}
      <input
        id={inputId}
        {...props}
        className={clsx(
          'bg-surface-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-100',
          'placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50',
          'disabled:opacity-50 disabled:cursor-not-allowed transition-colors',
          error && 'border-red-500/60',
          className,
        )}
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

export function Textarea({ label, error, className, id, ...props }: TextareaProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={inputId} className="text-xs font-medium text-gray-400">
          {label}
        </label>
      )}
      <textarea
        id={inputId}
        {...props}
        className={clsx(
          'bg-surface-900 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-100',
          'placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50',
          'disabled:opacity-50 disabled:cursor-not-allowed transition-colors resize-none',
          error && 'border-red-500/60',
          className,
        )}
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}
