import type { StatusHistoryPoint } from "../../libs/performance/history";
import { chartColors } from "../../libs/chartColors";
import { PerformanceChart } from "../PerformanceChart";

function efficiencyHistory(history: StatusHistoryPoint[]): StatusHistoryPoint[] {
  return history.map((point) => {
    const workerCapacity = Math.max(1, point.workerCapacity || point.workers || 1);
    const gpu = typeof point.gpu === "number" ? point.gpu : 0;
    const workerLoad = Math.min(100, (point.workers / workerCapacity) * 100);
    return {
      ...point,
      cpu: gpu,
      gpu: workerLoad,
      ram: point.workers,
      vram: workerCapacity,
    };
  });
}

export function BatchEfficiencyGraph({ history }: { history: StatusHistoryPoint[] }) {
  return (
    <PerformanceChart
      title="GPU batch efficiency"
      subtitle="GPU utilization beside document worker slot saturation."
      history={efficiencyHistory(history)}
      fixedMin={0}
      fixedMax={100}
      unit="%"
      series={[
        { key: "cpu", label: "GPU utilization", color: chartColors.orange, symbol: "triangle" },
        { key: "gpu", label: "Worker pressure", color: chartColors.green, lineType: "dashed", symbol: "diamond" },
      ]}
    />
  );
}
