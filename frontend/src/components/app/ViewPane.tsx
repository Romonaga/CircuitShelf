import type { ReactNode } from "react";
import type { View } from "../../types";

export function ViewPane({
  activeView,
  children,
  mounted,
  view,
}: {
  activeView: View;
  children: ReactNode;
  mounted: boolean;
  view: View;
}) {
  if (!mounted) {
    return null;
  }
  return <div hidden={activeView !== view}>{children}</div>;
}
