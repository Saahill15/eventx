import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "amber" | "ink" | "soft" | "outline" | "ghost";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  amber: "bg-ink text-white hover:bg-neutral-700",
  ink: "bg-ink text-white hover:bg-neutral-700",
  soft: "bg-chip text-chip-ink hover:bg-neutral-200",
  outline: "bg-white text-ink shadow-[var(--shadow-card)] hover:bg-wash",
  ghost: "text-mute hover:bg-black/5 hover:text-ink",
};
const sizes: Record<Size, string> = { sm: "h-9 px-4 text-sm", md: "h-11 px-6 text-[0.9375rem]", lg: "h-14 px-8 text-base" };

export function buttonClass(variant: Variant = "amber", size: Size = "md", extra = "") {
  return `inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-semibold transition active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${variants[variant]} ${sizes[size]} ${extra}`;
}

type Props = { variant?: Variant; size?: Size; href?: string; className?: string; children: ReactNode } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "className">;

export function Button({ variant = "amber", size = "md", href, className = "", children, ...rest }: Props) {
  const cls = buttonClass(variant, size, className);
  if (href) return <Link href={href} className={cls}>{children}</Link>;
  return <button className={cls} {...rest}>{children}</button>;
}
