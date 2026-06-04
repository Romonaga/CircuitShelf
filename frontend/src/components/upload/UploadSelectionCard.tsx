import type { UploadSelectionSummary } from "../../libs/upload/progress";

export function UploadSelectionCard({ selection }: { selection: UploadSelectionSummary }) {
  if (!selection.files.length) {
    return <p className="upload-selection muted">No files selected.</p>;
  }

  return (
    <div className="upload-selection-card" title={selection.title}>
      <div className="upload-selection-summary">
        <strong>{selection.label}</strong>
        <span>{selection.totalSize}</span>
      </div>
      <ul className="upload-selection-list" aria-label="Selected files">
        {selection.files.map((file, index) => (
          <li key={`${index}-${file.path}`} title={file.path}>
            <span className="upload-selection-name">{file.name}</span>
            {file.folder ? <span className="upload-selection-path">{file.folder}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
