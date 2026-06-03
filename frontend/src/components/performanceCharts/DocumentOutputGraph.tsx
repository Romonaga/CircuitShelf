import { useEffect, useMemo, useRef, useState } from "react";
import * as echarts from "echarts/core";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  ToolboxComponent,
  TooltipComponent
} from "echarts/components";
import { BarChart, LineChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";
import type { ComposeOption, EChartsType } from "echarts/core";
import type {
  DataZoomComponentOption,
  GridComponentOption,
  LegendComponentOption,
  ToolboxComponentOption,
  TooltipComponentOption
} from "echarts/components";
import type { BarSeriesOption, LineSeriesOption } from "echarts/charts";
import type { PerformanceWorkRun } from "../../types";
import { chartColors } from "../../lib/chartColors";
import { formatDurationMs, formatInteger, formatNumber } from "../../lib/format";
import { readChartTheme } from "../../lib/chartTheme";

echarts.use([
  BarChart,
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  LineChart,
  ToolboxComponent,
  TooltipComponent
]);

type ChartOption = ComposeOption<
  | BarSeriesOption
  | DataZoomComponentOption
  | GridComponentOption
  | LegendComponentOption
  | LineSeriesOption
  | ToolboxComponentOption
  | TooltipComponentOption
>;

interface OutputPoint {
  id: number | string;
  label: string;
  shortLabel: string;
  startedAt: string;
  durationMs: number;
  chunks: number;
  images: number;
  droppedChunks: number;
}

function basename(path: string) {
  const clean = path.replace(/\\/g, "/");
  return clean.split("/").filter(Boolean).pop() || clean;
}

function compactLabel(value: string) {
  const label = basename(value || "work");
  return label.length > 26 ? `${label.slice(0, 23)}...` : label;
}

function outputPoints(rows: PerformanceWorkRun[]): OutputPoint[] {
  return rows
    .filter((row) => row.workType !== "index_check")
    .filter((row) => row.status === "completed" || row.status === "skipped")
    .filter((row) => row.chunks > 0 || row.images > 0 || row.droppedChunks > 0)
    .slice(0, 24)
    .reverse()
    .map((row) => {
      const label = row.label || row.sourcePath || row.workTypeLabel || "work";
      return {
        id: row.id,
        label,
        shortLabel: compactLabel(label),
        startedAt: row.startedAt || "",
        durationMs: row.durationMs || 0,
        chunks: row.chunks || 0,
        images: row.images || 0,
        droppedChunks: row.droppedChunks || 0
      };
    });
}

export function DocumentOutputGraph({ rows }: { rows: PerformanceWorkRun[] }) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<EChartsType | null>(null);
  const [theme, setTheme] = useState(readChartTheme);
  const data = useMemo(() => outputPoints(rows), [rows]);
  const option = useMemo<ChartOption>(() => ({
    animation: false,
    color: [chartColors.blue, chartColors.orange, chartColors.vermillion, chartColors.green],
    grid: {
      left: 18,
      right: 58,
      top: 34,
      bottom: 96,
      containLabel: true
    },
    legend: {
      bottom: 30,
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
      iconStyle: { borderColor: theme.muted },
      emphasis: { iconStyle: { borderColor: theme.accent } }
    },
    tooltip: {
      trigger: "axis",
      confine: true,
      axisPointer: { type: "shadow" },
      formatter: (params) => {
        const first = Array.isArray(params) ? params[0] : params;
        const index = typeof first?.dataIndex === "number" ? first.dataIndex : 0;
        const row = data[index];
        const series = (Array.isArray(params) ? params : [params])
          .map((item) => {
            const value = Array.isArray(item.value) ? item.value[1] : item.value;
            return `${item.marker}${item.seriesName}: <strong>${formatNumber(typeof value === "number" ? value : null)}</strong>`;
          })
          .join("<br/>");
        return [
          `<strong>${row?.label ?? "work"}</strong>`,
          row?.startedAt ? new Date(row.startedAt).toLocaleString() : "",
          row?.durationMs ? `Duration: ${formatDurationMs(row.durationMs)}` : "",
          series
        ].filter(Boolean).join("<br/>");
      }
    },
    xAxis: {
      type: "category",
      data: data.map((row) => row.shortLabel),
      axisLabel: {
        color: theme.muted,
        interval: 0,
        rotate: data.length > 8 ? 28 : 0,
        hideOverlap: true
      },
      axisLine: { show: true, lineStyle: { color: theme.line, width: 1 } },
      axisTick: { show: true, lineStyle: { color: theme.line } },
      splitLine: { show: false }
    },
    yAxis: [
      {
        type: "value",
        name: "Items",
        min: 0,
        axisLabel: {
          color: theme.muted,
          formatter: (value: number) => formatInteger(value)
        },
        nameTextStyle: { color: theme.muted, fontWeight: 700 },
        axisLine: { show: true, lineStyle: { color: theme.line, width: 1 } },
        axisTick: { show: true, lineStyle: { color: theme.line } },
        splitLine: { show: true, lineStyle: { color: theme.splitLine, width: 1 } }
      },
      {
        type: "value",
        name: "Minutes",
        min: 0,
        axisLabel: {
          color: theme.muted,
          formatter: (value: number) => formatNumber(value)
        },
        nameTextStyle: { color: theme.muted, fontWeight: 700 },
        axisLine: { show: true, lineStyle: { color: theme.line, width: 1 } },
        axisTick: { show: true, lineStyle: { color: theme.line } },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: "inside",
        xAxisIndex: 0,
        filterMode: "none"
      },
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
    series: [
      {
        name: "Chunks",
        type: "bar",
        barMaxWidth: 22,
        data: data.map((row) => row.chunks)
      },
      {
        name: "Images",
        type: "bar",
        barMaxWidth: 22,
        data: data.map((row) => row.images)
      },
      {
        name: "Dropped chunks",
        type: "bar",
        barMaxWidth: 22,
        data: data.map((row) => row.droppedChunks)
      },
      {
        name: "Duration",
        type: "line",
        yAxisIndex: 1,
        symbolSize: 5,
        lineStyle: { width: 3 },
        data: data.map((row) => Number((row.durationMs / 60000).toFixed(2)))
      }
    ]
  }), [data, theme]);

  useEffect(() => {
    if (!chartRef.current || !data.length) {
      return;
    }
    const chart = echarts.init(chartRef.current, null, { renderer: "canvas" });
    chartInstanceRef.current = chart;
    const resizeObserver = new ResizeObserver(() => chart.resize());
    resizeObserver.observe(chartRef.current);
    const refreshTheme = () => setTheme(readChartTheme());
    const themeObserver = new MutationObserver(refreshTheme);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style", "data-theme"] });
    refreshTheme();
    return () => {
      themeObserver.disconnect();
      resizeObserver.disconnect();
      chart.dispose();
      chartInstanceRef.current = null;
    };
  }, [data.length]);

  useEffect(() => {
    chartInstanceRef.current?.setOption(option, true);
  }, [option]);

  return (
    <section className="performance-chart-card">
      <div className="performance-chart-heading">
        <div>
          <h3>Document output by job</h3>
          <p>Recent completed document work, showing generated chunks, image assets, dropped chunks, and duration.</p>
        </div>
        <span>{formatInteger(data.length)} jobs</span>
      </div>
      {data.length ? (
        <div ref={chartRef} className="performance-echart" role="img" aria-label="Document output by job" />
      ) : (
        <p className="empty-state">No completed document output has been recorded for this range.</p>
      )}
    </section>
  );
}
