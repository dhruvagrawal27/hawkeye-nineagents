import { cn } from '@/lib/format';

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'bg-slate-800/40 rounded animate-pulse',
        className,
      )}
    />
  );
}

export function SkeletonRow({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}
