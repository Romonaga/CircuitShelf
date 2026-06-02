import type { StatusHistoryPoint } from "../../hooks/useStatusHistory";
import { chartColors } from "../../lib/chartColors";
import { PerformanceChart } from "../PerformanceChart";

export function CatalogGrowthGraph({ history }: { history: StatusHistoryPoint[] }) {
  return (
    <PerformanceChart
      title="Catalog growth"
      subtitle="Indexed sources, text chunks, and image assets seen by status polling."
      history={history}
      series={[
        { key: "sources", label: "Sources", color: chartColors.navy },
        { key: "chunks", label: "Chunks", color: chartColors.green },
        { key: "images", label: "Images", color: chartColors.orange },
      ]}
    />
  );
}
