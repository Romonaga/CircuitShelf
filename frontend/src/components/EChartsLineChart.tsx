import { useEffect, useMemo, useRef, useState } from "react";
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
import type { ComposeOption, EChartsType } from "echarts/core";
import type {
  DataZoomComponentOption,
  GridComponentOption,
  LegendComponentOption,
  ToolboxComponentOption,
  TooltipComponentOption
} from "echarts/components";
import type { LineSeriesOption } from "echarts/charts";
import type { StatusHistoryPoint } from "../hooks/useStatusHistory";
import { formatNumber } from "../lib/format";
import { readChartTheme } from "../lib/chartTheme";
import type { ChartSeries } from "./PerformanceChart";

echarts.use([
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  LineChart,
  ToolboxComponent,
  TooltipComponent
]);

type ChartOption = ComposeOption<
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

export function EChartsLineChart({
  title,
  history,
  series,
  min,
  max,
  unit,
  labelMax,
  ceiling
}: {
  title: string;
  history: StatusHistoryPoint[];
  series: ChartSeries[];
  min: number;
  max: number;
  unit: string;
  labelMax?: number;
  ceiling?: number;
}) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<EChartsType | null>(null);
  const [theme, setTheme] = useState(readChartTheme);
  const option = useMemo<ChartOption>(() => ({
    animation: false,
    color: series.map((item) => item.color),
    grid: {
      left: 12,
      right: 32,
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
      valueFormatter: (value) => `${formatNumber(typeof value === "number" ? value : null)}${unit}`
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
    yAxis: {
      type: "value",
      min,
      max,
      axisLabel: {
        color: theme.muted,
        margin: 12,
        formatter: (value: number) => {
          if (typeof labelMax === "number" && value > labelMax) {
            return "";
          }
          return `${formatNumber(value)}${unit}`;
        }
      },
      axisLine: { show: true, lineStyle: { color: theme.line, width: 1 } },
      axisTick: { show: true, lineStyle: { color: theme.line } },
      splitLine: { show: true, lineStyle: { color: theme.splitLine, width: 1 } }
    },
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
    series: series.map((item, index) => ({
      name: item.label,
      type: "line",
      showSymbol: history.length <= 30,
      symbolSize: 4,
      smooth: false,
      sampling: "lttb",
      connectNulls: false,
      markLine:
        index === 0 && typeof ceiling === "number"
          ? {
              silent: true,
              symbol: "none",
              label: {
                formatter: `${formatNumber(ceiling)}${unit} ceiling`,
                color: theme.muted,
                fontWeight: 700,
                position: "insideEndTop"
              },
              lineStyle: {
                color: theme.line,
                width: 1,
                type: "dashed",
                opacity: 0.9
              },
              data: [{ yAxis: ceiling }]
            }
          : undefined,
      lineStyle: {
        width: 3,
        color: item.color
      },
      itemStyle: {
        color: item.color
      },
      emphasis: {
        focus: "series"
      },
      data: history.map((point) => {
        const value = point[item.key];
        return [
          point.sampledAt,
          typeof value === "number" && Number.isFinite(value) ? value : null
        ];
      })
    }))
  }), [ceiling, history, labelMax, max, min, series, theme, unit]);

  useEffect(() => {
    if (!chartRef.current) {
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
  }, []);

  useEffect(() => {
    chartInstanceRef.current?.setOption(option, true);
  }, [option]);

  return <div ref={chartRef} className="performance-echart" role="img" aria-label={title} />;
}
