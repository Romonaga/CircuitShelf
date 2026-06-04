import type { StatusHistoryPoint } from "../../hooks/useStatusHistory";
import { chartColors } from "../../libs/chartColors";
import { PerformanceChart } from "../PerformanceChart";

function efficiencyHistory(history: StatusHistoryPoint[]): StatusHistoryPoint[] {
  return history.map((point) => {
    const batchCapacity = Math.max(1, point.embeddingBatch + point.rerankerBatch);
    const gpu = typeof point.gpu === "number" ? point.gpu : 0;
    const workerLoad = Math.min(100, (point.workers / batchCapacity) * 100);
    return {
      ...point,
      cpu: gpu,
      gpu: workerLoad,
      ram: point.workers,
      vram: batchCapacity,
    };
  });
}

export function BatchEfficiencyGraph({ history }: { history: StatusHistoryPoint[] }) {
  return (
    <PerformanceChart
      title="GPU batch efficiency"
      subtitle="GPU utilization beside active document-worker pressure against selected batch capacity."
      history={efficiencyHistory(history)}
      fixedMin={0}
      fixedMax={100}
      unit="%"
      series={[
        { key: "cpu", label: "GPU utilization", color: chartColors.orange },
        { key: "gpu", label: "Worker pressure", color: chartColors.green },
      ]}
    />
  );
}
