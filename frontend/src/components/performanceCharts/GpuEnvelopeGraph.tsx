import type { StatusHistoryPoint } from "../../libs/performance/history";
import { chartColors } from "../../libs/chartColors";
import { PerformanceChart } from "../PerformanceChart";

export function GpuEnvelopeGraph({ history }: { history: StatusHistoryPoint[] }) {
  return (
    <PerformanceChart
      title="GPU envelope"
      subtitle="GPU compute, VRAM, thermal, and power pressure normalized onto one 0-100% scale."
      history={history}
      fixedMin={0}
      fixedMax={100}
      unit="%"
      series={[
        { key: "gpu", label: "GPU compute", color: chartColors.orange, symbol: "triangle" },
        { key: "vram", label: "VRAM", color: chartColors.purple, lineType: "dashed", symbol: "circle" },
        { key: "gpuTempLoad", label: "Temp pressure", color: chartColors.vermillion, lineType: "dotted", symbol: "diamond" },
        { key: "gpuPowerLoad", label: "Power pressure", color: chartColors.yellow, lineType: "dashed", symbol: "rect" },
      ]}
    />
  );
}
