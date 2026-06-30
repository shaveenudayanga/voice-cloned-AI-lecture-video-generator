// SPDX-License-Identifier: Apache-2.0
// @slow — requires a fully running stack (`make up`).
// Tests that DEPLOYMENT_MODE=web produces a working "Download video" button
// that triggers a browser file download for the assembled MP4.
//
// Run in isolation: pnpm exec playwright test --grep @slow
import { test, expect } from "@playwright/test";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const API_KEY = process.env.API_KEY ?? "test-api-key";

const headers = { "X-API-Key": API_KEY, "Content-Type": "application/json" };

// Minimal 3-byte valid MP4 stub — enough for the browser to create an object URL
// and for the download handler to call URL.createObjectURL.
const STUB_MP4 = Buffer.from([0x00, 0x00, 0x00, 0x08, 0x66, 0x74, 0x79, 0x70]);

test.describe("Web mode download @slow", () => {
  test("Done step renders Download video button and triggers file download", async ({
    page,
  }) => {
    // ── 1. Create a project via the API ─────────────────────────────────────
    const createRes = await page.request.post(`${API}/projects`, {
      headers,
      data: { title: "E2E Web Download Test" },
    });
    expect(createRes.status()).toBe(201);
    const project = (await createRes.json()) as { id: string; title: string };
    const pid = project.id;

    // ── 2. Intercept the blob proxy so we don't need real object storage ────
    //    The DoneStep calls GET /api/v1/blobs/<key> to fetch the MP4.
    //    We intercept it and return a stub so createObjectURL gets real bytes.
    const blobPattern = `**/api/v1/blobs/**`;
    await page.route(blobPattern, (route) =>
      route.fulfill({
        status: 200,
        contentType: "video/mp4",
        body: STUB_MP4,
      })
    );

    // ── 3. Intercept the video artifact endpoint to return a synthetic artifact
    await page.route(`**/api/v1/projects/${pid}/video`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "00000000-0000-0000-0000-000000000001",
          project_id: pid,
          video_blob_key: `projects/${pid}/output/video.mp4`,
          srt_blob_key: `projects/${pid}/output/video.srt`,
          total_duration_seconds: 30,
          slide_count: 1,
          ffmpeg_version: "7.0",
          created_at: new Date().toISOString(),
        }),
      })
    );

    // ── 4. Navigate directly to the Done wizard step ─────────────────────────
    //    The wizard reads step from the project's wizard_step field.
    //    We patch the project endpoint to return wizard_step=done so the
    //    stepper renders the Done step without walking through prior steps.
    await page.route(`**/api/v1/projects/${pid}`, (route, request) => {
      if (request.method() === "GET") {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: pid,
            user_id: "00000000-0000-0000-0000-000000000002",
            title: "E2E Web Download Test",
            wizard_step: "done",
            voice_profile_id: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.goto(`/projects/${pid}/wizard/done`);

    // ── 5. Wait for the Download video button ───────────────────────────────
    const downloadBtn = page.getByRole("button", { name: /download video/i });
    await expect(downloadBtn).toBeVisible({ timeout: 15_000 });
    // Button should be enabled once the video object URL is loaded
    await expect(downloadBtn).toBeEnabled({ timeout: 15_000 });

    // ── 6. Verify clicking it initiates a download (not a navigation) ───────
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 10_000 }),
      downloadBtn.click(),
    ]);

    // Filename should be sanitised project title + .mp4
    expect(download.suggestedFilename()).toMatch(/\.mp4$/);

    // ── 7. "Save to folder" must NOT be present in web mode ─────────────────
    await expect(
      page.getByRole("button", { name: /save to folder/i })
    ).not.toBeVisible();
  });
});
