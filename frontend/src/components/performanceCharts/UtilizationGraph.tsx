import type { StatusHistoryPoint } from "../../hooks/useStatusHistory";
import { chartColors } from "../../lib/chartColors";
import { PerformanceChart } from "../PerformanceChart";

export function UtilizationGraph({ history }: { history: StatusHistoryPoint[] }) {
  return (
    <PerformanceChart
      title="Operational pressure over time"
      subtitle="Seven normalized pressure signals on one scale: host, process, memory, GPU, VRAM, and active document workers."
      fixedMin={0}
      fixedMax={100}
      history={history}
      unit="%"
      series={[
        { key: "cpu", label: "System CPU", color: chartColors.blue },
        { key: "processCpuLoad", label: "Process CPU share", color: chartColors.cyan },
        { key: "ram", label: "RAM", color: chartColors.green },
        { key: "processRam", label: "Process RAM share", color: chartColors.navy },
        { key: "gpu", label: "GPU", color: chartColors.orange },
        { key: "vram", label: "VRAM", color: chartColors.purple },
        { key: "workerLoad", label: "Doc workers", color: chartColors.vermillion },
      ]}
    />
  );
}
