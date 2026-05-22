import { useEffect, useRef } from "react";
import type { DocumentSummary } from "../types";

export interface DocumentContextMenuState {
  document: DocumentSummary;
  x: number;
  y: number;
}

export function DocumentContextMenu({
  menu,
  removing,
  onClose,
  onRemove
}: {
  menu: DocumentContextMenuState | null;
  removing: boolean;
  onClose: () => void;
  onRemove: (document: DocumentSummary) => void;
}) {
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menu) {
      return;
    }

    const closeOnOutsideClick = (event: MouseEvent) => {
      if (menuRef.current?.contains(event.target as Node)) {
        return;
      }
      onClose();
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("keydown", closeOnEscape);
    window.addEventListener("scroll", onClose, true);
    return () => {
      window.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("scroll", onClose, true);
    };
  }, [menu, onClose]);

  if (!menu) {
    return null;
  }

  const displayName = menu.document.displayName ?? menu.document.source;
  const left = Math.max(8, Math.min(menu.x, window.innerWidth - 250));
  const top = Math.max(8, Math.min(menu.y, window.innerHeight - 118));

  return (
    <div ref={menuRef} className="document-context-menu" style={{ left, top }} role="menu">
      <div className="document-context-title">{displayName}</div>
      <button type="button" role="menuitem" className="danger-menu-item" onClick={() => onRemove(menu.document)} disabled={removing}>
        {removing ? "Removing..." : "Remove document"}
      </button>
    </div>
  );
}
