import {WORKPAL_MARK} from '../../lib/workpal-assets';
import { cn } from "../../lib/utils";
import { STAR_GRAPHIC_STROKE, starPath } from "../../lib/workpal-brand";

const STAR_STAGGER_S = 0.11;
/** Space between stars in a row, as a share of one star's width. */
const ROW_GAP = 0.4;
const THIN_STAR = starPath(STAR_GRAPHIC_STROKE);

interface WorkpalStarRowProps extends React.ComponentProps<"svg"> {
  /** Number of stars; each one stands for a teammate. */
  count: number;
  /**
   * Stars turn into place left to right and the last one arrives after a beat:
   * someone just joined. Omit for a static row.
   */
  join?: boolean;
  /** Seconds before the first star moves. */
  delay?: number;
  /** Classes for the last star, e.g. to light up the newest teammate. */
  lastClassName?: string;
}

/**
 * A row of thin stars, one per teammate — the star-field graphic from the
 * brand guidelines. Decorative and low-contrast; fill follows `currentColor`.
 */
export function WorkpalStarRow({
  count,
  join = false,
  delay = 0,
  lastClassName,
  className,
  ...props
}: WorkpalStarRowProps) {
  const step = 100 * (1 + ROW_GAP);
  const width = step * (count - 1) + 100;
  const delayOf = (i: number) => delay + i * STAR_STAGGER_S + (i === count - 1 ? 0.3 : 0);
  return (
    <svg
      viewBox={`0 0 ${width} 100`}
      fill="currentColor"
      aria-hidden="true"
      className={cn("block", className)}
      {...props}
    >
      {Array.from({ length: count }, (_, i) => (
        <g key={i} transform={`translate(${step * i} 0)`}>
          <image href={WORKPAL_MARK} width="100" height="100"/>
        </g>
      ))}
    </svg>
  );
}

interface WorkpalBleedMarkProps extends React.ComponentProps<"svg"> {
  /** Turn into place once, after this many seconds. Omit for static. */
  enterDelay?: number;
}

/**
 * A large thin star meant to bleed off the edges of its container — the big
 * graphic from the brand guidelines. Position it with `className`; fill
 * follows `currentColor`.
 */
export function WorkpalBleedMark({ enterDelay, className, ...props }: WorkpalBleedMarkProps) {
  return (
    <svg viewBox="0 0 100 100" fill="currentColor" aria-hidden="true" className={cn("block", className)} {...props}>
      <image href={WORKPAL_MARK} width="100" height="100"/>
    </svg>
  );
}
