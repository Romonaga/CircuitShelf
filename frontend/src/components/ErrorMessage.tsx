export function ErrorMessage({ message, className = "error" }: { message: string; className?: string }) {
  return message ? <div className={className}>{message}</div> : null;
}
