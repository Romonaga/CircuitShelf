import type { StatusHistoryPoint } from "../../libs/performance/history";
import { chartColors } from "../../libs/chartColors";
import { PerformanceChart } from "../PerformanceChart";

export function ThermalGraph({ history }: { history: StatusHistoryPoint[] }) {
  return (
    <PerformanceChart
      title="Thermals over time"
      subtitle="CPU and GPU temperature captured from the same persisted performance snapshots."
      history={history}
      fixedMin={0}
      unit=" C"
      series={[
        { key: "cpuTemp", label: "CPU temp", color: chartColors.vermillion },
        { key: "gpuTemp", label: "GPU temp", color: chartColors.orange },
      ]}
    />
  );
}
