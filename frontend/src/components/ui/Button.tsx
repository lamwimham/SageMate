import { forwardRef } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 rounded-[10px] font-medium text-[0.875rem] transition-all duration-200 cursor-pointer border whitespace-nowrap disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        primary:
          'bg-linear-to-br from-[#4f46e5] to-[#7c3aed] text-white border-transparent shadow-[0_2px_8px_rgba(79,70,229,0.25)] hover:shadow-[0_4px_16px_rgba(79,70,229,0.35)] hover:-translate-y-px active:translate-y-0',
        secondary:
          'bg-bg-elevated text-text-secondary border-border-medium hover:border-border-strong hover:text-text-primary hover:bg-bg-hover',
        ghost:
          'bg-transparent text-text-tertiary border-transparent hover:text-text-secondary hover:bg-black/[0.03]',
        danger:
          'bg-accent-danger/10 text-accent-danger border-accent-danger/20 hover:bg-accent-danger/20 hover:border-accent-danger/35',
        accent:
          'bg-linear-to-br from-[#6366f1] to-[#8b5cf6] text-white border-transparent shadow-[0_2px_8px_rgba(99,102,241,0.25)] hover:shadow-[0_4px_16px_rgba(99,102,241,0.35)] hover:-translate-y-px active:translate-y-0',
      },
      size: {
        default: 'px-4 py-2',
        sm: 'px-3 py-1.5 text-xs',
        lg: 'px-5 py-2.5 text-sm',
        icon: 'w-9 h-9 p-0',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'default',
    },
  }
)

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'
