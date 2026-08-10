import type { ReactNode } from "react";

import { classNames } from "@/lib/format";

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={classNames("card", className)}>{children}</section>;
}

export function CardHeader({
  title,
  subtitle,
  action,
  eyebrow,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  eyebrow?: string;
}) {
  return (
    <header className="flex items-start justify-between gap-4 border-b border-[var(--color-hairline)] px-5 py-4 sm:px-6">
      <div>
        {eyebrow ? (
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-indigo-400">
            {eyebrow}
          </p>
        ) : null}
        <h2 className="text-base font-semibold text-slate-100">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-sm muted">{subtitle}</p> : null}
      </div>
      {action}
    </header>
  );
}

export function Badge({
  children,
  className,
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={classNames(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        className ?? "border-[var(--color-hairline)] bg-slate-500/10 text-slate-300",
      )}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  disabled,
  className,
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  className?: string;
}) {
  const variants = {
    primary:
      "bg-indigo-500 text-white hover:bg-indigo-400 disabled:bg-indigo-500/40 disabled:text-white/60",
    ghost:
      "border border-[var(--color-hairline)] bg-transparent text-slate-300 hover:border-slate-500 hover:text-slate-100",
    danger:
      "border border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20",
  } as const;

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={classNames(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed",
        variants[variant],
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={classNames("h-4 w-4 animate-spin", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path
        d="M22 12a10 10 0 0 0-10-10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <p className="text-sm font-semibold text-slate-300">{title}</p>
      <p className="max-w-sm text-sm muted">{description}</p>
      {action}
    </div>
  );
}

export function Alert({
  tone = "error",
  title,
  children,
}: {
  tone?: "error" | "warning" | "info";
  title: string;
  children?: ReactNode;
}) {
  const tones = {
    error: "border-rose-500/30 bg-rose-500/10 text-rose-200",
    warning: "border-amber-500/30 bg-amber-500/10 text-amber-200",
    info: "border-indigo-500/30 bg-indigo-500/10 text-indigo-200",
  } as const;

  return (
    <div className={classNames("rounded-xl border px-4 py-3 text-sm", tones[tone])} role="alert">
      <p className="font-semibold">{title}</p>
      {children ? <div className="mt-1 opacity-90">{children}</div> : null}
    </div>
  );
}

/** Horizontal 0-100 meter used for per-agent signal strengths. */
export function Meter({
  value,
  className,
  label,
}: {
  value: number;
  className?: string;
  label?: string;
}) {
  const percent = Math.max(0, Math.min(100, value));
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-slate-700/50"
      role="meter"
      aria-valuenow={Math.round(percent)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div
        className={classNames("h-full rounded-full transition-[width] duration-500", className ?? "bg-indigo-400")}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
