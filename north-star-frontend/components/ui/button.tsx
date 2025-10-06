import * as React from "react";
import { clsx } from "clsx";
type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "outline" | "ghost" };
export const Button = React.forwardRef<HTMLButtonElement, Props>(({ className, variant="primary", ...props }, ref) => {
  const base = "rounded-2xl px-4 py-2 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action/90";
  const styles = { primary: "text-white bg-gradient-to-r from-action via-blue-400 to-subtlePurple hover:brightness-110 shadow-soft hover:shadow-lift", outline: "border border-white/20 hover:bg-white/5 text-text", ghost: "hover:bg-white/5 text-text" } as const;
  return <button ref={ref} className={clsx(base, styles[variant], className)} {...props} />;
});
Button.displayName="Button";
