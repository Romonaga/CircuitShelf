import type { StatusHistoryPoint } from "../../hooks/useStatusHistory";
import { chartColors } from "../../lib/chartColors";
import { PerformanceChart } from "../PerformanceChart";

export function PowerGraph({ history }: { history: StatusHistoryPoint[] }) {
  return (
    <PerformanceChart
      title="Power usage over time"
      subtitle="CPU package and NVIDIA GPU power draw captured from persisted performance snapshots."
      history={history}
      fixedMin={0}
      unit=" W"
      series={[
        { key: "cpuPower", label: "CPU package", color: chartColors.blue },
        { key: "gpuPower", label: "GPU", color: chartColors.orange },
      ]}
    />
  );
}
