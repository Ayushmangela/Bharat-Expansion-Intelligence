import { describe, expect, it } from "vitest";
import { formatMonthLabel } from "./chart-colors";

describe("formatMonthLabel", () => {
  it("formats a full ISO date to short month/year", () => {
    expect(formatMonthLabel("2025-06-01")).toBe("Jun 25");
  });

  it("formats a year-month string without a day component", () => {
    expect(formatMonthLabel("2025-06")).toBe("Jun 25");
  });

  it("returns the input unchanged when it can't be parsed as a date", () => {
    expect(formatMonthLabel("not-a-date")).toBe("not-a-date");
  });
});
