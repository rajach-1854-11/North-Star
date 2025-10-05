import * as React from "react";
import { clsx } from "clsx";

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...props }, ref) => (
  <select
    ref={ref}
    className={clsx(
      "w-full rounded-2xl border border-white/25 bg-white/10 px-3 py-2 text-sm font-medium text-white/95 backdrop-blur transition-colors",
      "placeholder:text-white/70 focus:text-white focus:outline-none focus:ring-2 focus:ring-white/50 focus:border-white/70",
      className
    )}
    {...props}
  />
));

Select.displayName = "Select";
