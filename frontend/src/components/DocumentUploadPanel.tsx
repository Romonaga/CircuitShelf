import { useEffect, useRef, useState } from "react";
import { uploadDocuments, type UploadProgress } from "../api";
import { errorMessage } from "../lib/errors";
import { formatBytes, formatDurationMs, formatInteger } from "../lib/format";
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
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [localError, setLocalError] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const uploadStartedAtRef = useRef<number | null>(null);

  const isDisabled = disabled || uploading;
  const selection = summarizeSelection(files);

  function resetSelection() {
    setFiles([]);
    setProgress(null);
    setInputKey((key) => key + 1);
  }

  function acceptSelection(fileList: FileList | null) {
    setLocalError("");
    setProgress(null);
    onError("");
    setFiles(Array.from(fileList ?? []));
  }

  async function submitUpload() {
    if (!files.length || isDisabled) {
      return;
    }
    setUploading(true);
    uploadStartedAtRef.current = performance.now();
    setProgress({
      loaded: 0,
      total: files.reduce((sum, file) => sum + file.size, 0),
      percent: 0,
      computable: true,
      bytesPerSecond: null,
      etaSeconds: null,
      elapsedSeconds: 0
    });
    setLocalError("");
    onError("");
    try {
      const response = await uploadDocuments(files, overwrite, scope, (nextProgress) => {
        setProgress(nextProgress);
      });
      onUploaded(uploadResultMessage(response));
      resetSelection();
      onStatusChange();
    } catch (err) {
      const message = errorMessage(err, "Upload failed");
      setLocalError(message);
      onError(message);
    } finally {
      setUploading(false);
      uploadStartedAtRef.current = null;
    }
  }

  useEffect(() => {
    if (!uploading) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      const startedAt = uploadStartedAtRef.current;
      if (!startedAt) {
        return;
      }
      const elapsedSeconds = Math.max((performance.now() - startedAt) / 1000, 0);
      setProgress((current) => {
        if (!current) {
          return current;
        }
        const bytesPerSecond = elapsedSeconds > 0.2 && current.loaded > 0 ? current.loaded / elapsedSeconds : current.bytesPerSecond ?? null;
        const etaSeconds =
          bytesPerSecond && current.total > current.loaded && current.percent < 100 ? (current.total - current.loaded) / bytesPerSecond : null;
        return {
          ...current,
          bytesPerSecond,
          etaSeconds,
          elapsedSeconds
        };
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [uploading]);

  const uploadEtaLabel = progress ? formatEta(progress.etaSeconds, progress.percent) : "calculating";

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
      ) : (
        <p className="upload-selection muted">No files selected.</p>
      )}
      <label className="checkbox-label">
        <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} disabled={isDisabled} />
        Replace existing
      </label>
      <button className="primary-button" onClick={submitUpload} disabled={!files.length || isDisabled}>
        {uploading ? `Uploading · ${uploadEtaLabel}` : files.length > 1 ? `Upload ${formatInteger(files.length)} files` : "Upload"}
      </button>
      {uploading && progress ? (
        <div className="upload-progress" role="status" aria-live="polite">
          <div className="upload-progress-headline">
            <span>
              <small>Estimated time left</small>
              <strong>{formatUploadEta(progress.etaSeconds, progress.percent)}</strong>
            </span>
            <span>
              <small>Elapsed</small>
              <strong>{formatDurationMs((progress.elapsedSeconds ?? 0) * 1000)}</strong>
            </span>
          </div>
          <div className="upload-progress-bar">
            <span style={{ width: `${progress.percent}%` }} />
          </div>
          <p>
            Uploading {formatInteger(files.length)} file{files.length === 1 ? "" : "s"} · {progress.percent}% · ETA {uploadEtaLabel} ·{" "}
            {formatBytes(progress.loaded)} / {progress.total > 0 ? formatBytes(progress.total) : "unknown size"}
          </p>
          <div className="upload-progress-stats">
            <span>
              <small>Speed</small>
              <strong>{formatUploadSpeed(progress.bytesPerSecond)}</strong>
            </span>
            <span>
              <small>ETA</small>
              <strong>{formatEta(progress.etaSeconds, progress.percent)}</strong>
            </span>
            <span>
              <small>Elapsed</small>
              <strong>{formatDurationMs((progress.elapsedSeconds ?? 0) * 1000)}</strong>
            </span>
          </div>
        </div>
      ) : null}
      <ErrorMessage message={localError} />
    </div>
  );
}

function formatUploadSpeed(bytesPerSecond: number | null | undefined) {
  if (!bytesPerSecond || !Number.isFinite(bytesPerSecond)) {
    return "calculating";
  }
  return `${formatBytes(bytesPerSecond)}/s`;
}

function formatEta(seconds: number | null | undefined, percent: number) {
  if (percent >= 100) {
    return "server processing";
  }
  if (!seconds || !Number.isFinite(seconds)) {
    return "calculating";
  }
  return formatDurationMs(seconds * 1000);
}

function formatUploadEta(seconds: number | null | undefined, percent: number) {
  if (percent >= 100) {
    return "Waiting for server";
  }
  if (!seconds || !Number.isFinite(seconds)) {
    return "Calculating ETA";
  }
  return `${formatDurationMs(seconds * 1000)} left`;
}

function summarizeSelection(files: File[]) {
  if (!files.length) {
    return { label: "No files selected.", title: "", totalSize: "", files: [] };
  }
  const selectedFiles = files.map((file) => {
    const path = file.webkitRelativePath || file.name;
    const parts = path.split("/");
    const name = parts.pop() || path;
    return {
      path,
      name,
      folder: parts.join("/")
    };
  });
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  return {
    label: `${formatInteger(files.length)} selected`,
    totalSize: formatBytes(totalBytes),
    files: selectedFiles,
    title: selectedFiles.map((file) => file.path).join("\n")
  };
}
