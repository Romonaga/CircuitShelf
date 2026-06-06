import { formatInteger } from "../../libs/format";
import {
  chunkProgress,
  compactPhase,
  fileSizeProgress,
  formatDetailValue,
  imageProgress,
  pageProgress,
  phaseTone,
  type IngestProgress
} from "../../libs/ingest/format";

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
        <span className="ingest-file-cell ingest-file-cell-name">File ({formatInteger(rows.length)})</span>
        <span className="ingest-file-cell ingest-file-cell-size">Size</span>
        <span className="ingest-file-cell ingest-file-cell-phase">Phase</span>
        <span className="ingest-file-cell ingest-file-cell-page">Page</span>
        <span className="ingest-file-cell ingest-file-cell-chunks">Chunks</span>
        <span className="ingest-file-cell ingest-file-cell-images">Images</span>
      </div>
      {rows.map(({ file, progress }) => (
        <div key={file} className="ingest-file-row">
          <strong className="ingest-file-cell ingest-file-cell-name" title={file}>{file}</strong>
          <span className="ingest-file-cell ingest-file-cell-size ingest-table-number" title={fileSizeProgress(progress)}>
            {fileSizeProgress(progress)}
          </span>
          <span className="ingest-file-cell ingest-file-cell-phase">
            <span className={`ingest-phase-badge ${phaseTone(progress)}`} title={formatDetailValue(progress.documentPhase ?? "Active")}>
              {compactPhase(progress)}
            </span>
          </span>
          <span className="ingest-file-cell ingest-file-cell-page ingest-table-number" title={pageProgress(progress)}>
            {pageProgress(progress)}
          </span>
          <span className="ingest-file-cell ingest-file-cell-chunks ingest-table-number" title={chunkProgress(progress)}>
            {chunkProgress(progress)}
          </span>
          <span className="ingest-file-cell ingest-file-cell-images ingest-table-number" title={imageProgress(progress)}>
            {imageProgress(progress)}
          </span>
        </div>
      ))}
    </div>
  );
}
