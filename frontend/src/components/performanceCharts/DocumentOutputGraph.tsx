import { useEffect, useMemo } from "react";
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
import type { PerformanceWorkRun } from "../../types";
import { formatInteger } from "../../libs/format";
import {
  buildDocumentOutputOption,
  outputPoints,
  type DocumentOutputChartOption
} from "../../libs/performanceCharts/documentOutput";
import { useEChart } from "../../hooks/charts/useEChart";

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

export function DocumentOutputGraph({ rows }: { rows: PerformanceWorkRun[] }) {
  const data = useMemo(() => outputPoints(rows), [rows]);
  const { chartRef, setOption, theme } = useEChart<DocumentOutputChartOption>({ enabled: data.length > 0 });
  const option = useMemo(() => buildDocumentOutputOption(data, theme), [data, theme]);

  useEffect(() => {
    setOption(option);
  }, [option, setOption]);

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
