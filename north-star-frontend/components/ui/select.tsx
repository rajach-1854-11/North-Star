import * as React from "react";
import { clsx } from "clsx";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...props }, ref) => (
  <select
    ref={ref}
    className={clsx(
      "w-full rounded-2xl border border-white/15 bg-white/[.08] px-3 py-2 text-sm font-medium text-white placeholder:text-white/60 transition-colors",
      "hover:border-white/40 focus:outline-none focus:ring-2 focus:ring-white/40 focus:border-white/60",
      className
    )}
    {...props}
  />
));

Select.displayName = "Select";
