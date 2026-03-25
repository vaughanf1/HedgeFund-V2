import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-zinc-700 text-zinc-100 hover:bg-zinc-600',
        secondary:
          'border-transparent bg-zinc-800 text-zinc-300 hover:bg-zinc-700',
        destructive:
          'border-transparent bg-red-900 text-red-300 hover:bg-red-800',
        outline: 'text-zinc-100 border-zinc-700',
        success:
          'border-transparent bg-emerald-900 text-emerald-300',
        warning:
          'border-transparent bg-amber-900 text-amber-300',
        running:
          'border-transparent bg-blue-900 text-blue-300',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
