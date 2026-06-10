import { useEffect, useMemo } from "react";
import * as echarts from "echarts/core";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  TooltipComponent
} from "echarts/components";
import { LineChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";
import type { ComposeOption } from "echarts/core";
import type {
  DataZoomComponentOption,
  GridComponentOption,
  LegendComponentOption,
  ToolboxComponentOption,
  TooltipComponentOption
} from "echarts/components";
import type { LineSeriesOption } from "echarts/charts";
import type { StatusHistoryPoint } from "../../libs/performance/history";
import { chartColors } from "../../libs/chartColors";
import { formatInteger, formatNumber } from "../../libs/format";
import { useEChart } from "../../hooks/charts/useEChart";

echarts.use([
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  LineChart,
  ToolboxComponent,
  TooltipComponent
]);

type QueueChartOption = ComposeOption<
  | DataZoomComponentOption
  | GridComponentOption
  | LegendComponentOption
  | LineSeriesOption
  | ToolboxComponentOption
  | TooltipComponentOption
>;

function formatTime(value: number) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function maxValue(history: StatusHistoryPoint[], keys: Array<keyof StatusHistoryPoint>) {
  const values = history.flatMap((point) =>
    keys
      .map((key) => point[key])
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
  );
  return values.length ? Math.max(...values) : 0;
}

function dataFor(history: StatusHistoryPoint[], key: keyof StatusHistoryPoint) {
  return history.map((point) => {
    const value = point[key];
    return [point.sampledAt, typeof value === "number" && Number.isFinite(value) ? value : null];
  });
}

const queueSeries = [
  { name: "Queued total", key: "gpuQueueQueued", yAxisIndex: 0, color: chartColors.orange, lineType: "solid", symbol: "circle" },
  { name: "Active total", key: "gpuQueueActive", yAxisIndex: 0, color: chartColors.blue, lineType: "dashed", symbol: "triangle" },
  { name: "CUDA queued", key: "gpuQueueCudaQueued", yAxisIndex: 0, color: chartColors.purple, lineType: "dotted", symbol: "rect" },
  { name: "OCR queued", key: "gpuQueueOcrQueued", yAxisIndex: 0, color: chartColors.green, lineType: "dashed", symbol: "diamond" },
  { name: "LLM queued", key: "gpuQueueLlmQueued", yAxisIndex: 0, color: chartColors.vermillion, lineType: "dotted", symbol: "triangle" },
  { name: "Oldest wait", key: "gpuQueueCurrentWaitSeconds", yAxisIndex: 1, color: chartColors.yellow, lineType: "solid", symbol: "circle" },
  { name: "Recent avg wait", key: "gpuQueueRecentAvgWaitSeconds", yAxisIndex: 1, color: chartColors.cyan, lineType: "dashed", symbol: "rect" },
  { name: "Recent max wait", key: "gpuQueueRecentMaxWaitSeconds", yAxisIndex: 1, color: chartColors.slate, lineType: "dotted", symbol: "diamond" },
] as const;

function swatchBackground(color: string, lineType: string) {
  if (lineType === "dashed") {
    return `repeating-linear-gradient(90deg, ${color} 0 8px, transparent 8px 13px)`;
  }
  if (lineType === "dotted") {
    return `repeating-linear-gradient(90deg, ${color} 0 3px, transparent 3px 8px)`;
  }
  return color;
}

export function GpuQueueGraph({ history }: { history: StatusHistoryPoint[] }) {
  const { chartRef, setOption, theme } = useEChart<QueueChartOption>();
  const latest = history[history.length - 1];
  const maxQueue = maxValue(history, [
    "gpuQueueQueued",
    "gpuQueueActive",
    "gpuQueueCudaQueued",
    "gpuQueueOcrQueued",
    "gpuQueueLlmQueued",
  ]);
  const maxWait = maxValue(history, [
    "gpuQueueCurrentWaitSeconds",
    "gpuQueueRecentAvgWaitSeconds",
    "gpuQueueRecentMaxWaitSeconds",
  ]);
  const option = useMemo<QueueChartOption>(() => ({
    animation: false,
    color: queueSeries.map((item) => item.color),
    grid: {
      left: 12,
      right: 64,
      top: 28,
      bottom: 76,
      containLabel: true
    },
    legend: {
      bottom: 24,
      left: 8,
      type: "scroll",
      textStyle: {
        color: theme.muted,
        fontWeight: 700
      },
      pageIconColor: theme.accent,
      pageTextStyle: {
        color: theme.muted
      }
    },
    toolbox: {
      top: 0,
      right: 0,
      itemSize: 16,
      feature: {
        dataZoom: { yAxisIndex: "none" },
        restore: {},
        saveAsImage: { pixelRatio: 2 }
      },
      iconStyle: {
        borderColor: theme.muted
      },
      emphasis: {
        iconStyle: {
          borderColor: theme.accent
        }
      }
    },
    tooltip: {
      trigger: "axis",
      confine: true,
      valueFormatter: (value) => formatNumber(typeof value === "number" ? value : null)
    },
    xAxis: {
      type: "time",
      min: "dataMin",
      max: "dataMax",
      axisLabel: {
        color: theme.muted,
        formatter: (value: number) => formatTime(value),
        hideOverlap: true,
        showMaxLabel: false
      },
      axisLine: { show: true, lineStyle: { color: theme.line, width: 1 } },
      axisTick: { show: true, lineStyle: { color: theme.line } },
      splitLine: { show: false }
    },
    yAxis: [
      {
        type: "value",
        name: "items",
        min: 0,
        max: Math.max(2, Math.ceil(maxQueue * 1.2)),
        axisLabel: { color: theme.muted },
        nameTextStyle: { color: theme.muted, fontWeight: 700 },
        axisLine: { show: true, lineStyle: { color: theme.line, width: 1 } },
        axisTick: { show: true, lineStyle: { color: theme.line } },
        splitLine: { show: true, lineStyle: { color: theme.splitLine, width: 1 } }
      },
      {
        type: "value",
        name: "wait sec",
        min: 0,
        max: Math.max(5, Math.ceil(maxWait * 1.2)),
        axisLabel: { color: theme.muted },
        nameTextStyle: { color: theme.muted, fontWeight: 700 },
        axisLine: { show: true, lineStyle: { color: theme.line, width: 1 } },
        axisTick: { show: true, lineStyle: { color: theme.line } },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: 0, filterMode: "none" },
      {
        type: "slider",
        xAxisIndex: 0,
        height: 18,
        bottom: 3,
        filterMode: "none",
        borderColor: theme.line,
        fillerColor: "rgba(65, 199, 178, 0.18)",
        handleStyle: {
          color: theme.accent,
          borderColor: theme.accent
        },
        textStyle: {
          color: theme.muted
        }
      }
    ],
    series: queueSeries.map((item) => ({
      name: item.name,
      type: "line",
      yAxisIndex: item.yAxisIndex,
      showSymbol: history.length <= 30,
      symbol: item.symbol,
      symbolSize: item.symbol === "diamond" || item.symbol === "triangle" ? 7 : 5,
      smooth: false,
      sampling: "lttb",
      connectNulls: false,
      lineStyle: { width: item.yAxisIndex ? 2 : 3, color: item.color, type: item.lineType },
      itemStyle: { color: item.color },
      emphasis: { focus: "series" },
      data: dataFor(history, item.key as keyof StatusHistoryPoint)
    }))
  }), [history, maxQueue, maxWait, theme]);

  useEffect(() => {
    setOption(option);
  }, [option, setOption]);

  return (
    <section className="performance-chart-card">
      <div className="performance-chart-heading">
        <div>
          <h3>GPU queue pressure</h3>
          <p>Queued GPU work, active lanes, and time spent waiting for local GPU resources.</p>
        </div>
        <span>{formatInteger(history.length)} samples</span>
      </div>
      <div ref={chartRef} className="performance-echart" role="img" aria-label="GPU queue pressure" />
      <div className="chart-legend">
        <span><i style={{ background: swatchBackground(chartColors.orange, "solid") }} />Queued<strong>{formatInteger(latest?.gpuQueueQueued)}</strong></span>
        <span><i style={{ background: swatchBackground(chartColors.blue, "dashed") }} />Active<strong>{formatInteger(latest?.gpuQueueActive)}</strong></span>
        <span><i style={{ background: swatchBackground(chartColors.yellow, "solid") }} />Oldest wait<strong>{formatNumber(latest?.gpuQueueCurrentWaitSeconds)}s</strong></span>
        {latest ? <small className="chart-latest-time">Latest {new Date(latest.sampledAt).toLocaleString()}</small> : null}
      </div>
    </section>
  );
}

export default GpuQueueGraph;
