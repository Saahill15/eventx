import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "dark" | "glass" | "ghost";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "bg-hive text-ink shadow-[0_6px_20px_rgba(245,163,0,0.35)] hover:bg-hive-dark",
  dark: "bg-ink text-white hover:bg-neutral-700",
  glass: "glass text-ink hover:bg-white/80",
  ghost: "text-neutral-600 hover:bg-black/5",
};
const sizes: Record<Size, string> = {
  sm: "h-9 px-4 text-sm",
  md: "h-11 px-6 text-[0.9375rem]",
  lg: "h-13 px-8 text-base",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra = "") {
  return `inline-flex items-center justify-center gap-2 rounded-full font-semibold transition active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-hive ${variants[variant]} ${sizes[size]} ${extra}`;
}

type Props = {
  variant?: Variant;
  size?: Size;
  href?: string;
  className?: string;
  children: ReactNode;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className">;

export function Button({ variant = "primary", size = "md", href, className = "", children, ...rest }: Props) {
  const cls = buttonClass(variant, size, className);
  if (href) return <Link href={href} className={cls}>{children}</Link>;
  return <button className={cls} {...rest}>{children}</button>;
}
