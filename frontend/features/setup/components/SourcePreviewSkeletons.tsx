export function SourceGroupsSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 7 }).map((_, index) => (
        <div className="flex items-center gap-3 rounded-2xl p-2" key={index}>
          <div className="size-10 shrink-0 animate-pulse rounded-full bg-muted dark:bg-white/10" />
          <div className="h-4 w-24 animate-pulse rounded-full bg-muted dark:bg-white/10" />
          <div className="ml-auto size-8 shrink-0 animate-pulse rounded-full bg-muted dark:bg-white/10" />
        </div>
      ))}
    </div>
  );
}

export function MessagePreviewSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, index) => (
        <div className="mx-auto flex w-full max-w-140 items-start gap-2" key={index}>
          <div className="mt-3 size-9 shrink-0 animate-pulse rounded-full bg-muted dark:bg-white/10" />
          <div className="min-w-0 flex-1 overflow-hidden rounded-[1rem] border border-border bg-background shadow-sm dark:border-white/10 dark:bg-[#111d2a]">
            <div className="flex items-center gap-2 px-3 pt-3">
              <div className="h-3.5 w-24 animate-pulse rounded-full bg-sky-200 dark:bg-sky-400/25" />
              <div className="ml-auto size-5 shrink-0 animate-pulse rounded-full bg-sky-200 dark:bg-sky-400/25" />
            </div>
            <div className="space-y-3 p-3">
              <div className="space-y-2.5">
                <div className="h-3.5 w-11/12 animate-pulse rounded-full bg-muted dark:bg-white/10" />
                <div className="h-3.5 w-3/4 animate-pulse rounded-full bg-muted dark:bg-white/10" />
                <div className="h-3.5 w-5/6 animate-pulse rounded-full bg-muted dark:bg-white/10" />
              </div>
              {index % 2 === 1 ? (
                <div className="flex gap-3 rounded-lg border-l-2 border-sky-300 bg-muted/60 p-2 dark:border-sky-500/50 dark:bg-white/5">
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="h-3 w-16 animate-pulse rounded-full bg-sky-200 dark:bg-sky-400/25" />
                    <div className="h-3 w-11/12 animate-pulse rounded-full bg-muted-foreground/20 dark:bg-white/10" />
                    <div className="h-3 w-2/3 animate-pulse rounded-full bg-muted-foreground/20 dark:bg-white/10" />
                  </div>
                  <div className="size-14 shrink-0 animate-pulse rounded-md bg-muted dark:bg-white/10" />
                </div>
              ) : null}
              <div className="flex items-center gap-2">
                <div className="h-3 w-20 animate-pulse rounded-full bg-sky-200 dark:bg-sky-400/25" />
                <div className="ml-auto h-3 w-28 animate-pulse rounded-full bg-muted dark:bg-white/10" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
