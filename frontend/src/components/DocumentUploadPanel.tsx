import { useRef, useState } from "react";
import { uploadDocuments } from "../api";
import { errorMessage } from "../lib/errors";
import { formatInteger } from "../lib/format";
import { uploadResultMessage } from "../lib/uploadMessages";
import { ErrorMessage } from "./ErrorMessage";

type UploadScope = "entity" | "global";

interface DocumentUploadPanelProps {
  scope: UploadScope;
  disabled?: boolean;
  help?: string;
  onUploaded: (message: string) => void;
  onError: (message: string) => void;
  onStatusChange: () => void;
}

export function DocumentUploadPanel({
  scope,
  disabled = false,
  help,
  onUploaded,
  onError,
  onStatusChange
}: DocumentUploadPanelProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [inputKey, setInputKey] = useState(0);
  const [overwrite, setOverwrite] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [localError, setLocalError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);

  const isDisabled = disabled || uploading;
  const selection = summarizeSelection(files);

  function resetSelection() {
    setFiles([]);
    setInputKey((key) => key + 1);
  }

  function acceptSelection(fileList: FileList | null) {
    setLocalError("");
    onError("");
    setFiles(Array.from(fileList ?? []));
  }

  async function submitUpload() {
    if (!files.length || isDisabled) {
      return;
    }
    setUploading(true);
    setLocalError("");
    onError("");
    try {
      const response = await uploadDocuments(files, overwrite, scope);
      onUploaded(uploadResultMessage(response));
      resetSelection();
      onStatusChange();
    } catch (err) {
      const message = errorMessage(err, "Upload failed");
      setLocalError(message);
      onError(message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="upload-panel">
      {help ? <p className="upload-help">{help}</p> : null}
      <div className="upload-picker-actions">
        <button className="ghost-button" type="button" onClick={() => fileInputRef.current?.click()} disabled={isDisabled}>
          Choose files
        </button>
        <button className="ghost-button" type="button" onClick={() => folderInputRef.current?.click()} disabled={isDisabled}>
          Choose folder
        </button>
      </div>
      <input
        key={`files-${inputKey}`}
        ref={fileInputRef}
        className="hidden-file-input"
        type="file"
        multiple
        onChange={(event) => acceptSelection(event.target.files)}
        disabled={isDisabled}
      />
      <input
        key={`folder-${inputKey}`}
        ref={(element) => {
          folderInputRef.current = element;
          element?.setAttribute("webkitdirectory", "");
          element?.setAttribute("directory", "");
        }}
        className="hidden-file-input"
        type="file"
        multiple
        onChange={(event) => acceptSelection(event.target.files)}
        disabled={isDisabled}
      />
      {files.length ? (
        <p className="upload-selection" title={selection.title}>
          {selection.label}
        </p>
      ) : (
        <p className="upload-selection muted">No files selected.</p>
      )}
      <label className="checkbox-label">
        <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} disabled={isDisabled} />
        Replace existing
      </label>
      <button className="primary-button" onClick={submitUpload} disabled={!files.length || isDisabled}>
        {uploading ? "Uploading..." : files.length > 1 ? `Upload ${formatInteger(files.length)} files` : "Upload"}
      </button>
      <ErrorMessage message={localError} />
    </div>
  );
}

function summarizeSelection(files: File[]) {
  if (!files.length) {
    return { label: "No files selected.", title: "" };
  }
  const names = files.map((file) => file.webkitRelativePath || file.name);
  const firstNames = names.slice(0, 4).join(", ");
  const extra = names.length > 4 ? `, +${formatInteger(names.length - 4)} more` : "";
  return {
    label: `${formatInteger(files.length)} selected: ${firstNames}${extra}`,
    title: names.join("\n")
  };
}
