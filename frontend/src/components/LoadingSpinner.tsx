export function LoadingSpinner({ className = "" }: { className?: string }) {
  const classes = ["loading-spinner", className].filter(Boolean).join(" ");
  return <span className={classes} aria-hidden="true" />;
}
