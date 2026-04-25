import { useEffect, useRef, useState, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { Button } from './Button'

export type BannerVariant = 'success' | 'error' | 'info'

export interface BannerAction {
  label: string
  onClick: () => void
  variant?: 'primary' | 'secondary'
}

interface InlineBannerProps {
  variant: BannerVariant
  title?: string
  message: string
  actions?: BannerAction[]
  autoClose?: number // ms, default 5000, 0 = never auto-close
  onClose?: () => void
  className?: string
}

const variantStyles: Record<BannerVariant, string> = {
  success:
    'bg-accent-living/8 border-accent-living/20',
  error:
    'bg-accent-danger/8 border-accent-danger/20',
  info:
    'bg-accent-neural/8 border-accent-neural/20',
}

const iconStyles: Record<BannerVariant, string> = {
  success: 'text-accent-living',
  error: 'text-accent-danger',
  info: 'text-accent-neural',
}

const iconPaths: Record<BannerVariant, string> = {
  success: 'M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4 12 14.01 9 11.01',
  error: 'M18 6 6 18 M6 6l12 12',
  info: 'M12 16v-4 M12 8h.01 M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z',
}

export function InlineBanner({
  variant,
  title,
  message,
  actions,
  autoClose = 5000,
  onClose,
  className,
}: InlineBannerProps) {
  const [visible, setVisible] = useState(false)
  const [hovered, setHovered] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const remainingRef = useRef(autoClose)
  const startRef = useRef(Date.now())

  // Entrance animation
  useEffect(() => {
    const r = requestAnimationFrame(() => setVisible(true))
    return () => cancelAnimationFrame(r)
  }, [])

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const startTimer = useCallback(() => {
    if (autoClose <= 0) return
    clearTimer()
    startRef.current = Date.now()
    timerRef.current = setTimeout(() => {
      setVisible(false)
      setTimeout(() => onClose?.(), 300) // wait for exit animation
    }, remainingRef.current)
  }, [autoClose, onClose, clearTimer])

  // Auto-close logic with hover pause
  useEffect(() => {
    if (!hovered) {
      startTimer()
    } else {
      // Pause: subtract elapsed from remaining
      const elapsed = Date.now() - startRef.current
      remainingRef.current = Math.max(0, remainingRef.current - elapsed)
      clearTimer()
    }
    return () => clearTimer()
  }, [hovered, startTimer, clearTimer])

  const handleClose = () => {
    clearTimer()
    setVisible(false)
    setTimeout(() => onClose?.(), 300)
  }

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={cn(
        'rounded-xl border px-4 py-3.5 transition-all duration-300',
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2',
        variantStyles[variant],
        className
      )}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className={cn('w-5 h-5 shrink-0 mt-0.5', iconStyles[variant])}
        >
          <path d={iconPaths[variant]} />
        </svg>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {title && (
            <div className="text-sm font-semibold text-text-primary mb-0.5">
              {title}
            </div>
          )}
          <div className="text-sm text-text-secondary leading-relaxed">
            {message}
          </div>

          {/* Actions */}
          {actions && actions.length > 0 && (
            <div className="flex items-center gap-2 mt-2.5">
              {actions.map((action, i) => (
                <Button
                  key={i}
                  variant={action.variant ?? 'secondary'}
                  size="sm"
                  onClick={action.onClick}
                >
                  {action.label}
                </Button>
              ))}
            </div>
          )}
        </div>

        {/* Close */}
        {autoClose !== 0 && (
          <button
            onClick={handleClose}
            className="shrink-0 p-1 rounded-md text-text-muted hover:text-text-secondary hover:bg-black/[0.05] transition"
            aria-label="关闭"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-4 h-4"
            >
              <path d="M18 6 6 18 M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}
