import { describe, expect, it } from "vitest";
import { getFrontendConfig } from "./config";

describe("getFrontendConfig", () => {
  it("returns default localhost API URL when env is empty", () => {
    const config = getFrontendConfig();
    expect(config.apiBaseUrl).toBe("http://localhost:8000");
  });

  it("never includes server secrets", () => {
    const config = getFrontendConfig();
    const configObj = config as unknown as Record<string, unknown>;
    expect(configObj.MODEL_API_KEY).toBeUndefined();
    expect(configObj.AWS_SECRET_ACCESS_KEY).toBeUndefined();
    expect(configObj.SUPABASE_SERVICE_ROLE_KEY).toBeUndefined();
  });
});
