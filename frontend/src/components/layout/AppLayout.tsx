import { NavLink, Outlet } from 'react-router-dom'
import { LayoutDashboard, GitBranch, Settings, Cpu } from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: <LayoutDashboard size={16} /> },
  { to: '/studio', label: 'Studio', icon: <GitBranch size={16} /> },
]

export function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-surface-900">
      {/* Sidebar */}
      <nav
        className="w-14 shrink-0 bg-surface-800 border-r border-white/10 flex flex-col items-center py-3 gap-1"
        aria-label="Main navigation"
      >
        {/* Logo mark */}
        <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center mb-3 shrink-0">
          <Cpu size={16} className="text-white" />
        </div>

        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            title={item.label}
            className={({ isActive }) =>
              clsx(
                'w-9 h-9 flex items-center justify-center rounded-lg transition-colors',
                isActive
                  ? 'bg-brand-500/20 text-brand-500'
                  : 'text-gray-500 hover:text-white hover:bg-white/5',
              )
            }
            aria-label={item.label}
          >
            {item.icon}
          </NavLink>
        ))}

        <div className="flex-1" />

        <NavLink
          to="/settings"
          title="Settings"
          className={({ isActive }) =>
            clsx(
              'w-9 h-9 flex items-center justify-center rounded-lg transition-colors',
              isActive
                ? 'bg-brand-500/20 text-brand-500'
                : 'text-gray-500 hover:text-white hover:bg-white/5',
            )
          }
          aria-label="Settings"
        >
          <Settings size={16} />
        </NavLink>
      </nav>

      {/* Main content */}
      <main className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
