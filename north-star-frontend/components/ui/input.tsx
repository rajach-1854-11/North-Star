import * as React from "react";
import { clsx } from "clsx";
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input ref={ref} className={clsx("w-full rounded-2xl bg-white/[.04] backdrop-blur border border-white/10 px-3 py-2 transition-colors hover:border-white/20", className)} {...props} />
));
Input.displayName="Input";
