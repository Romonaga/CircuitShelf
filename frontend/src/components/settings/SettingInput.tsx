import type { AppSetting, SettingValue } from "../../types";

export function SettingInput({
  setting,
  value,
  onChange
}: {
  setting: AppSetting;
  value: SettingValue;
  onChange: (value: SettingValue) => void;
}) {
  const options = settingOptions(setting.key);
  if (options.length > 0) {
    return (
      <select value={String(value ?? options[0].value)} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  if (setting.valueType === "boolean") {
    return (
      <select value={String(value)} onChange={(event) => onChange(event.target.value === "true")}>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    );
  }

  if (setting.valueType === "integer" || setting.valueType === "numeric") {
    return (
      <input
        type="number"
        step={setting.valueType === "integer" ? "1" : "any"}
        value={String(value)}
        onChange={(event) => onChange(setting.valueType === "integer" ? Number.parseInt(event.target.value || "0", 10) : Number(event.target.value))}
      />
    );
  }

  const stringValue = String(value ?? "");
  if (stringValue.length > 120 || stringValue.includes("\n")) {
    return <textarea rows={10} value={stringValue} onChange={(event) => onChange(event.target.value)} />;
  }
  return <input value={stringValue} onChange={(event) => onChange(event.target.value)} />;
}

function settingOptions(key: string): Array<{ value: string; label: string }> {
  if (key === "OCR_ENGINE") {
    return [
      { value: "tesseract", label: "Tesseract (stable CPU)" },
      { value: "paddleocr", label: "PaddleOCR (CPU, GPU experimental)" }
    ];
  }
  if (key === "PADDLEOCR_DEVICE") {
    return [
      { value: "gpu", label: "GPU" },
      { value: "cpu", label: "CPU" }
    ];
  }
  return [];
}
