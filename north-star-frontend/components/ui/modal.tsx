import * as React from "react";
export function Modal({ title, onClose, children }: React.PropsWithChildren<{title: string; onClose: ()=>void;}>) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div role="dialog" aria-modal className="w-full max-w-3xl rounded-2xl border border-white/10 bg-panel shadow-2xl">
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
          <div className="text-lg font-semibold">{title}</div>
          <button onClick={onClose} className="text-sm text-meta hover:text-white">Close</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
