import { Card, CardHeader } from "@/components/ui/primitives";

export function RecommendedActions({ actions }: { actions: string[] }) {
  if (actions.length === 0) return null;

  return (
    <Card className="border-indigo-500/25 bg-indigo-500/[0.06]">
      <CardHeader
        eyebrow="What to do next"
        title="Recommended actions"
        subtitle="Concrete steps, in order of importance."
      />
      <ol className="card-pad space-y-3">
        {actions.map((action, index) => (
          <li key={index} className="flex gap-3">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-xs font-bold text-indigo-200">
              {index + 1}
            </span>
            <p className="text-sm leading-relaxed text-slate-200">{action}</p>
          </li>
        ))}
      </ol>
    </Card>
  );
}
