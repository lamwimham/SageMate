import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon?: string
  title: string
  description?: string
  action?: {
    to: string
    label: string
    icon?: React.ReactNode
  }
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('card py-16 text-center animate-fade-up', className)}>
      {icon && <div className="text-5xl mb-4 opacity-40">{icon}</div>}
      <h3 className="text-lg font-medium mb-1 text-text-primary">{title}</h3>
      {description && <p className="text-sm mb-5 text-text-tertiary">{description}</p>}
      {action && (
        <Link
          to={action.to}
          className="btn btn-primary text-sm inline-flex items-center gap-1.5"
        >
          {action.icon}
          {action.label}
        </Link>
      )}
    </div>
  )
}
