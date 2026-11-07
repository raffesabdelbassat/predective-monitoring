import { render, screen } from "@testing-library/react";
import axios from "axios";
import { vi } from "vitest";
import App from "./App";

vi.mock("axios");

const responses = {
  "/metrics?limit=100": [],
  "/metrics/latest": { message: "No metrics recorded yet" },
  "/alerts": { alert_count: 0, alerts: [] },
  "/predictions/anomaly": { status: "not enough data", min_required: 10, have: 0 },
  "/predictions/forecast?hours=1": { status: "not enough data", min_required: 10, have: 0 },
  "/health/score": { score: null, status: "no data" },
  "/alerts/history?limit=50": [],
  "/predictions/failure": { samples_used: 0 },
  "/processes?limit=5": [],
  "/alerts/config": { cpu_threshold: 90, memory_threshold: 95, disk_threshold: 90 },
};

beforeEach(() => {
  axios.get.mockImplementation((url) => {
    const path = new URL(url).pathname + new URL(url).search;
    const response = Object.entries(responses).find(([key]) => path.endsWith(key));
    return Promise.resolve({ data: response ? response[1] : null });
  });
});

test("renders an empty dashboard while waiting for the first readings", async () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: /predictive monitoring/i })).toBeInTheDocument();
  expect(await screen.findByText("No metrics to chart")).toBeInTheDocument();
  expect(screen.getByText("Waiting for readings")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /save thresholds/i })).toBeInTheDocument();
});
