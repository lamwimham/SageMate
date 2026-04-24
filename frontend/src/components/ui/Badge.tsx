import { cn } from '@/lib/utils'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'entity' | 'concept' | 'analysis' | 'source' | 'note' | 'neural' | 'growth' | 'living' | 'danger' | 'warm'
  className?: string
}

const variantStyles: Record<string, string> = {
  default: 'bg-bg-elevated text-text-tertiary',
  entity: 'bg-cat-entity/10 text-cat-entity',
  concept: 'bg-cat-concept/10 text-cat-concept',
  analysis: 'bg-cat-analysis/10 text-cat-analysis',
  source: 'bg-cat-source/10 text-cat-source',
  note: 'bg-accent-growth/10 text-accent-growth',
  neural: 'bg-accent-neural/10 text-accent-neural',
  growth: 'bg-accent-growth/10 text-accent-growth',
  living: 'bg-accent-living/10 text-accent-living',
  danger: 'bg-accent-danger/10 text-accent-danger',
  warm: 'bg-accent-warm/10 text-accent-warm',
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span className={cn('badge', variantStyles[variant] || variantStyles.default, className)}>
      {children}
    </span>
  )
}
