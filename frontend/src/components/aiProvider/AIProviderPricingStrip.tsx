import type { AIModelPricing } from "../../types";

export function AIProviderPricingStrip({ price }: { price?: AIModelPricing }) {
  if (!price) {
    return null;
  }

  return (
    <div className="pricing-strip">
      <span>Input ${price.inputPerMillion}/1M</span>
      <span>Cached ${price.cachedInputPerMillion}/1M</span>
      <span>Output ${price.outputPerMillion}/1M</span>
    </div>
  );
}
