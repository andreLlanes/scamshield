"use client";

import { useState } from "react";

import { AnalysisList } from "@/components/history/AnalysisList";
import { Alert, Card, CardHeader } from "@/components/ui/primitives";
import { ApiError, api } from "@/lib/api";
import { useAnalysisList } from "@/lib/hooks";

export default function HistoryPage() {
  const { items, total, isLoading, error, refresh } = useAnalysisList(50);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const remove = async (id: string) => {
    setDeleteError(null);
    try {
      await api.deleteAnalysis(id);
      await refresh();
    } catch (caught) {
      setDeleteError(
        caught instanceof ApiError ? caught.message : "Could not delete that analysis.",
      );
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-50">Analysis history</h1>
        <p className="mt-1 text-sm muted">
          Every call you have analysed on this ScamShield instance.
        </p>
      </div>

      {error ? <Alert title="Could not load history">{error}</Alert> : null}
      {deleteError ? <Alert title="Delete failed">{deleteError}</Alert> : null}

      <Card>
        <CardHeader
          title="All analyses"
          subtitle={`${total} ${total === 1 ? "recording" : "recordings"} analysed`}
        />
        <AnalysisList items={items} isLoading={isLoading} onDelete={remove} />
      </Card>
    </div>
  );
}
