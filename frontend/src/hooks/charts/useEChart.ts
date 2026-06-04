import { useCallback, useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import type { EChartsType } from "echarts/core";
import { readChartTheme, type ChartTheme } from "../../libs/chartTheme";

type EChartOption = Parameters<EChartsType["setOption"]>[0];

export function useEChart<TOption extends EChartOption>({ enabled = true }: { enabled?: boolean } = {}) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<EChartsType | null>(null);
  const [theme, setTheme] = useState<ChartTheme>(readChartTheme);

  useEffect(() => {
    if (!enabled || !chartRef.current) {
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
  }, [enabled]);

  const setOption = useCallback((option: TOption) => {
    chartInstanceRef.current?.setOption(option, true);
  }, []);

  return {
    chartRef,
    setOption,
    theme
  };
}
