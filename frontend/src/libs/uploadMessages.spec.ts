import { expect, test } from "@playwright/test";

import { uploadResultMessage } from "./uploadMessages";
import type { UploadDocumentsResponse } from "../types";

function uploadResponse(skippedFiles: UploadDocumentsResponse["skippedFiles"]): UploadDocumentsResponse {
  return {
    ok: true,
    files: [{ filename: "SIM7080G_Cat_M_NB_IoT_HAT_Code/Arduino/SIM7080G_PING_Demo/sim7080g_ping_demo.ino", bytes: 42 }],
    skippedFiles,
    count: 21,
    skippedCount: skippedFiles.length,
    bytes: 42,
    indexing: { started: true }
  };
}

test("upload result message keeps large skipped reason categories visible", () => {
  const skippedFiles = [
    ...Array.from({ length: 61 }, (_, index) => ({
      filename: `SIM7080G_Cat_M_NB_IoT_HAT_Code/STM32/SIM7080G_TCP_Test_Demo.7z:Drivers/vendor_${index}.h`,
      reason: "ignored generated/vendor dependency file"
    })),
    ...Array.from({ length: 39 }, (_, index) => ({
      filename: `unsupported_${index}.ioc`,
      reason: "Unsupported file type. Allowed: .c, .h, .ino, .py, .sh"
    })),
    ...Array.from({ length: 12 }, (_, index) => ({
      filename: `.git/internal_${index}`,
      reason: "ignored project/internal file"
    }))
  ];

  const message = uploadResultMessage(uploadResponse(skippedFiles));

  expect(message).toContain("21 files uploaded.");
  expect(message).toContain("112 files skipped");
  expect(message).toContain("ignored generated/vendor dependency file (61)");
  expect(message).toContain("Unsupported file type (39)");
  expect(message).toContain("ignored project/internal file (12)");
  expect(message).toContain("+109 more");
  expect(message).toContain("Incremental indexing started");
});
