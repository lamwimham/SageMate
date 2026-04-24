/**
 * Animation system constants — single source of truth for all motion design.
 *
 * Matches DESIGN_LANGUAGE.md §6 动效系统
 */

export const EASING = {
  outExpo: 'cubic-bezier(0.16, 1, 0.3, 1)',
  inOutSine: 'cubic-bezier(0.37, 0, 0.63, 1)',
  spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
} as const

export const DURATION = {
  fast: 150,
  normal: 300,
  slow: 400,
  entrance: 400,
  scaleIn: 300,
  glowPulse: 2000,
  borderFlow: 3000,
  shimmer: 1500,
  numberTick: 600,
} as const

export const STAGGER = {
  step: 50,
  max: 5,
} as const

/**
 * Generate stagger delay class name
 */
export function staggerClass(index: number): string {
  const n = Math.min(Math.max(index, 0), STAGGER.max)
  return `stagger-${n + 1}`
}

/**
 * Generate fade-up animation with optional stagger
 */
export function fadeUpClass(index?: number): string {
  const base = 'animate-fade-up'
  if (index === undefined) return base
  return `${base} ${staggerClass(index)}`
}
