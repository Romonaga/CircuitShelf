import { useEffect, useRef } from "react";

export interface DocumentMenuItem {
  source: string;
  displayName?: string;
}

export interface DocumentContextMenuState {
  document: DocumentMenuItem;
  x: number;
  y: number;
}

export function DocumentContextMenu({
  menu,
  removing,
  reindexing,
  onClose,
  onReindex,
  onRemove
}: {
  menu: DocumentContextMenuState | null;
  removing: boolean;
  reindexing?: boolean;
  onClose: () => void;
  onReindex?: (document: DocumentMenuItem) => void;
  onRemove: (document: DocumentMenuItem) => void;
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
  const top = Math.max(8, Math.min(menu.y, window.innerHeight - 164));
  const busy = Boolean(removing || reindexing);

  return (
    <div ref={menuRef} className="document-context-menu" style={{ left, top }} role="menu">
      <div className="document-context-title">{displayName}</div>
      {onReindex ? (
        <button type="button" role="menuitem" onClick={() => onReindex(menu.document)} disabled={busy}>
          {reindexing ? "Queueing re-index..." : "Re-index document"}
        </button>
      ) : null}
      <button type="button" role="menuitem" className="danger-menu-item" onClick={() => onRemove(menu.document)} disabled={busy}>
        {removing ? "Removing..." : "Remove document"}
      </button>
    </div>
  );
}
