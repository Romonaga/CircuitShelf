export function UploadPickerActions({
  disabled,
  onChooseFiles,
  onChooseFolder
}: {
  disabled: boolean;
  onChooseFiles: () => void;
  onChooseFolder: () => void;
}) {
  return (
    <div className="upload-picker-actions">
      <button className="ghost-button" type="button" onClick={onChooseFiles} disabled={disabled}>
        Choose files
      </button>
      <button className="ghost-button" type="button" onClick={onChooseFolder} disabled={disabled}>
        Choose folder
      </button>
    </div>
  );
}
