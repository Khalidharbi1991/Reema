import { Skeleton } from "@/components/Card";

/** Skeleton while Today loads; no spinners. */
export default function TodayLoading() {
  return (
    <div className="mt-4" aria-busy="true">
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-9 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-1/3" />
        </div>
        <Skeleton className="h-[76px] w-[76px] rounded-full" />
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}
