import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ConfidenceBadge from "./ConfidenceBadge";

describe("ConfidenceBadge", () => {
  it("renders the band label and percentage", () => {
    render(<ConfidenceBadge band="High" score={1.0} />);
    expect(screen.getByText("High · 100%")).toBeInTheDocument();
  });

  it("renders a Low band for a weak score", () => {
    render(<ConfidenceBadge band="Low" score={0.1137} />);
    // matches the real Niuland scorecard verified live in-browser this session
    expect(screen.getByText("Low · 11%")).toBeInTheDocument();
  });

  it("falls back to the Unknown style for an unrecognised band without crashing", () => {
    render(<ConfidenceBadge band="Nonexistent" score={0.5} />);
    expect(screen.getByText("Nonexistent · 50%")).toBeInTheDocument();
  });
});
