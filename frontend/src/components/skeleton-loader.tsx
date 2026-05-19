"use client";

function Bone({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-surface-sunken ${className ?? ""}`}
    />
  );
}

export function SidebarSkeleton() {
  return (
    <div className="space-y-3 px-3 py-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex items-center gap-2 px-2">
          <Bone className="h-4 w-4 shrink-0 rounded" />
          <Bone className="h-4 flex-1" />
        </div>
      ))}
    </div>
  );
}

export function ChatSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      {/* Assistant message skeleton */}
      <div className="flex items-start gap-3">
        <div className="space-y-2">
          <Bone className="h-4 w-48" />
          <Bone className="h-4 w-64" />
          <Bone className="h-4 w-40" />
        </div>
      </div>
      {/* User message skeleton */}
      <div className="flex justify-end">
        <Bone className="h-10 w-36 rounded-xl" />
      </div>
      {/* Assistant message skeleton */}
      <div className="flex items-start gap-3">
        <div className="space-y-2">
          <Bone className="h-4 w-56" />
          <Bone className="h-4 w-44" />
        </div>
      </div>
    </div>
  );
}
