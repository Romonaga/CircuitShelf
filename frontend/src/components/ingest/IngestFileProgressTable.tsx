import { formatInteger } from "../../lib/format";
import {
  chunkProgress,
  compactPhase,
  formatDetailValue,
  imageProgress,
  pageProgress,
  phaseTone,
  type IngestProgress
} from "../../lib/ingest/format";

export interface IngestFileRow {
  file: string;
  progress: IngestProgress;
}

export function IngestFileProgressTable({ running, rows }: { running: boolean; rows: IngestFileRow[] }) {
  if (!running || !rows.length) {
    return null;
  }

  return (
    <div className="ingest-file-grid">
      <div className="ingest-file-grid-heading">
        <span>File ({formatInteger(rows.length)})</span>
        <span>Phase</span>
        <span>Page</span>
        <span>Chunks</span>
        <span>Images</span>
      </div>
      {rows.map(({ file, progress }) => (
        <div key={file} className="ingest-file-row">
          <strong title={file}>{file}</strong>
          <span className={`ingest-phase-badge ${phaseTone(progress)}`} title={formatDetailValue(progress.documentPhase ?? "Active")}>
            {compactPhase(progress)}
          </span>
          <span className="ingest-table-number">{pageProgress(progress)}</span>
          <span className="ingest-table-number">{chunkProgress(progress)}</span>
          <span className="ingest-table-number">{imageProgress(progress)}</span>
        </div>
      ))}
    </div>
  );
}
