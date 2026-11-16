import type { ReactNode } from "react";

/**
 * Snafi's icons (docs/UI.md 4.9): inline SVG drawn for Snafi, one stroke weight, no icon library
 * and no glyphs. Always decorative: the name is on the button or link, never on the icon.
 */
function Icon({ size, className, children }: { size: number; className?: string; children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={1.5}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={className}>
      {children}
    </svg>
  );
}

type Props = { className?: string };

export const BellIcon = () => (
  <Icon size={24}><path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15l1.5-2Z" /><path d="M10 20.5a2 2 0 0 0 4 0" /></Icon>
);
/** Mirrors in Arabic. */
export const BackIcon = () => <Icon size={24} className="icon-mirror"><path d="M19 12H5" /><path d="M11 6l-6 6 6 6" /></Icon>;
export const ChevronDownIcon = ({ className }: Props) => <Icon size={20} className={className}><path d="M6 9l6 6 6-6" /></Icon>;
/** Mirrors in Arabic. */
export const ChevronForwardIcon = ({ className = "" }: Props) => (
  <Icon size={20} className={`icon-mirror ${className}`}><path d="M9 6l6 6-6 6" /></Icon>
);
export const ArrowDownIcon = () => <Icon size={24}><path d="M12 5v14" /><path d="M6 13l6 6 6-6" /></Icon>;
export const TaskCircleIcon = ({ className }: Props) => <Icon size={16} className={className}><circle cx="12" cy="12" r="7.25" /></Icon>;
export const AttentionIcon = () => (
  <Icon size={16}><circle cx="12" cy="12" r="8.25" /><path d="M12 8v4.5" /><path d="M12 15.75v.01" /></Icon>
);
