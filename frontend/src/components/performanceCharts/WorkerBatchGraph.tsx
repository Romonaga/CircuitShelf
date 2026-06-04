import type { StatusHistoryPoint } from "../../hooks/useStatusHistory";
import { chartColors } from "../../libs/chartColors";
import { PerformanceChart } from "../PerformanceChart";

export function WorkerBatchGraph({ history }: { history: StatusHistoryPoint[] }) {
  return (
    <PerformanceChart
      title="Active document workers"
      subtitle="Document workers plus the active embedding and reranker batch sizes."
      history={history}
      series={[
        { key: "workers", label: "Active doc workers", color: chartColors.green },
        { key: "embeddingBatch", label: "Embedding batch", color: chartColors.blue },
        { key: "rerankerBatch", label: "Reranker batch", color: chartColors.purple },
      ]}
    />
  );
}
