import type { StatusPayload } from "../../types";
import type { StatusHistoryPoint } from "../../libs/performance/history";
import { formatBytes, formatInteger, formatNumber, formatPercent } from "../../libs/format";
import { Stat } from "../Stat";

export function PerformanceStatsGrid({
  resources,
  peaks,
  peakWorkers
}: {
  resources: StatusPayload["systemResources"];
  peaks: Partial<Record<keyof StatusHistoryPoint, number | null>>;
  peakWorkers: number;
}) {
  const gpu = resources?.gpu;
  const process = resources?.process;
  const runtimePeaks = resources?.peaks;

  return (
    <div className="status-grid performance-stats">
      <Stat label="CPU cores" value={formatInteger(resources?.cpu?.cores)} />
      <Stat label="System CPU" value={formatPercent(resources?.cpu?.utilizationPercent)} />
      <Stat label="Process CPU" value={formatPercent(process?.cpuPercent)} />
      <Stat label="Process RAM" value={formatBytes(process?.memoryBytes)} />
      <Stat label="CPU temp" value={typeof resources?.cpu?.temperatureC === "number" ? `${formatNumber(resources.cpu.temperatureC)} C` : "n/a"} />
      <Stat label="CPU power" value={typeof resources?.cpu?.powerW === "number" ? `${formatNumber(resources.cpu.powerW)} W` : "n/a"} />
      <Stat label="GPU" value={gpu?.available ? formatPercent(gpu.utilizationPercent) : "n/a"} />
      <Stat label="GPU temp" value={gpu?.available && typeof gpu.temperatureC === "number" ? `${formatNumber(gpu.temperatureC)} C` : "n/a"} />
      <Stat label="GPU power" value={gpu?.available && typeof gpu.powerW === "number" ? `${formatNumber(gpu.powerW)} W` : "n/a"} />
      <Stat label="VRAM" value={gpu?.available ? `${formatNumber(gpu.memoryUsedMiB)} MiB` : "n/a"} />
      <Stat label="Window peak CPU" value={formatPercent(peaks.cpu)} />
      <Stat label="Window peak GPU" value={formatPercent(peaks.gpu)} />
      <Stat label="Today peak CPU" value={formatPercent(runtimePeaks?.cpuPercent)} />
      <Stat label="Today peak CPU temp" value={typeof runtimePeaks?.cpuTemperatureC === "number" ? `${formatNumber(runtimePeaks.cpuTemperatureC)} C` : "n/a"} />
      <Stat label="Today peak CPU power" value={typeof runtimePeaks?.cpuPowerW === "number" ? `${formatNumber(runtimePeaks.cpuPowerW)} W` : "n/a"} />
      <Stat label="Today peak process" value={formatPercent(runtimePeaks?.processCpuPercent)} />
      <Stat label="Today peak GPU" value={formatPercent(runtimePeaks?.gpuPercent)} />
      <Stat label="Today peak GPU temp" value={typeof runtimePeaks?.gpuTemperatureC === "number" ? `${formatNumber(runtimePeaks.gpuTemperatureC)} C` : "n/a"} />
      <Stat label="Today peak VRAM" value={formatPercent(runtimePeaks?.gpuMemoryUsedPercent)} />
      <Stat label="Today peak doc workers" value={formatInteger(peakWorkers)} />
      <Stat label="Today peak RAM" value={formatPercent(runtimePeaks?.memoryUsedPercent)} />
    </div>
  );
}
