import { describe, expect, it } from "vitest";
import { formatFileSize, formatINR, formatINRCompact } from "@/lib/format";

describe("formatINR", () => {
  it("uses Indian digit grouping", () => {
    expect(formatINR(1234567)).toBe("₹12,34,567");
  });
});

describe("formatINRCompact", () => {
  it("formats lakh and crore", () => {
    expect(formatINRCompact(412300)).toBe("₹4.1 L");
    expect(formatINRCompact(18425000)).toBe("₹1.8 Cr");
    expect(formatINRCompact(85000)).toBe("₹85,000");
    expect(formatINRCompact(500000)).toBe("₹5 L");
  });
});

describe("formatFileSize", () => {
  it("formats bytes, KB and MB", () => {
    expect(formatFileSize(500)).toBe("500 B");
    expect(formatFileSize(2048)).toBe("2 KB");
    expect(formatFileSize(5 * 1024 * 1024)).toBe("5 MB");
    expect(formatFileSize(1.5 * 1024 * 1024)).toBe("1.5 MB");
  });
});
