import type { StatusHistoryPoint } from "../../libs/performance/history";
import { chartColors } from "../../libs/chartColors";
import { PerformanceChart } from "../PerformanceChart";

export function UtilizationGraph({ history }: { history: StatusHistoryPoint[] }) {
  return (
    <PerformanceChart
      title="Operational pressure over time"
      subtitle="Seven normalized pressure signals on one scale: host, process, memory, GPU, VRAM, and document worker slot utilization."
      fixedMin={0}
      fixedMax={100}
      history={history}
      unit="%"
      series={[
        { key: "cpu", label: "System CPU", color: chartColors.blue, symbol: "circle" },
        { key: "processCpuLoad", label: "App CPU share", color: chartColors.navy, lineType: "dashed", symbol: "triangle" },
        { key: "ram", label: "RAM", color: chartColors.green, symbol: "diamond" },
        { key: "processRam", label: "App RAM share", color: chartColors.cyan, lineType: "dotted", symbol: "rect" },
        { key: "gpu", label: "GPU", color: chartColors.orange, symbol: "triangle" },
        { key: "vram", label: "VRAM", color: chartColors.purple, lineType: "dashed", symbol: "circle" },
        { key: "workerLoad", label: "Worker slots", color: chartColors.vermillion, lineType: "dotted", symbol: "diamond" },
      ]}
    />
  );
}
