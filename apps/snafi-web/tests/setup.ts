import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Offline only: any network call from a test fails loudly.
const blocked = () => {
  throw new Error("Network access is forbidden in Snafi tests");
};
vi.stubGlobal("fetch", blocked);

afterEach(() => {
  cleanup();
});
