import { useEffect, useRef, useState } from "react";
import { uploadDocuments, type UploadProgress } from "../libs/api";
import { errorMessage } from "../libs/errors";
import { formatInteger } from "../libs/format";
import { formatUploadEta, summarizeSelection } from "../libs/upload/progress";
import { uploadResultMessage } from "../libs/uploadMessages";
import { ErrorMessage } from "./ErrorMessage";
import { UploadPickerActions } from "./upload/UploadPickerActions";
import { UploadProgressPanel } from "./upload/UploadProgressPanel";
import { UploadSelectionCard } from "./upload/UploadSelectionCard";

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

  const uploadEtaLabel = progress ? formatUploadEta(progress.etaSeconds, progress.percent) : "calculating";

  return (
    <div className="upload-panel">
      {help ? <p className="upload-help">{help}</p> : null}
      <UploadPickerActions
        disabled={isDisabled}
        onChooseFiles={() => fileInputRef.current?.click()}
        onChooseFolder={() => folderInputRef.current?.click()}
      />
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
      <UploadSelectionCard selection={selection} />
      <label className="checkbox-label">
        <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} disabled={isDisabled} />
        Replace existing
      </label>
      <button className="primary-button" onClick={submitUpload} disabled={!files.length || isDisabled}>
        {uploading ? `Uploading · ${uploadEtaLabel}` : files.length > 1 ? `Upload ${formatInteger(files.length)} files` : "Upload"}
      </button>
      {uploading && progress ? <UploadProgressPanel filesCount={files.length} progress={progress} /> : null}
      <ErrorMessage message={localError} />
    </div>
  );
}
