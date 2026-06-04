import type { StatusPayload } from "../../types";
import { formatBytes, formatNumber } from "../../libs/format";
import { MetricBar } from "../MetricBar";

export function LiveResourcePressure({ resources }: { resources: StatusPayload["systemResources"] }) {
  const gpu = resources?.gpu;
  const memory = resources?.memory;
  const process = resources?.process;
  const processCpuMax = Math.max(100, (resources?.cpu?.cores ?? 1) * 100);

  return (
    <section className="resource-panel">
      <div>
        <h3>Live resource pressure</h3>
        <p>{gpu?.available ? gpu.name : "No NVIDIA telemetry available"}</p>
      </div>
      <MetricBar label="CPU" value={resources?.cpu?.utilizationPercent} tone="blue" />
      <MetricBar label="Process CPU" value={process?.cpuPercent} max={processCpuMax} tone="green" />
      <MetricBar label="RAM" value={memory?.usedPercent} detail={`${formatBytes(memory?.usedBytes)} / ${formatBytes(memory?.totalBytes)}`} tone="teal" />
      <MetricBar label="GPU" value={gpu?.available ? gpu.utilizationPercent : null} tone="orange" />
      <MetricBar
        label="VRAM"
        value={gpu?.available ? gpu.memoryUsedPercent : null}
        detail={gpu?.available ? `${formatNumber(gpu.memoryUsedMiB)} / ${formatNumber(gpu.memoryTotalMiB)} MiB` : "n/a"}
        tone="teal"
      />
    </section>
  );
}
