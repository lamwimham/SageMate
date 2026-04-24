import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, icon, ...props }, ref) => {
    return (
      <div className="relative w-full">
        {icon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-text-muted">
            {icon}
          </div>
        )}
        <input
          ref={ref}
          className={cn('input', icon && 'pl-10', className)}
          {...props}
        />
      </div>
    )
  }
)
Input.displayName = 'Input'
