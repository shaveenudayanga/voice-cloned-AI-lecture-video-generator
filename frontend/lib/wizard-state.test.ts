// SPDX-License-Identifier: Apache-2.0
// Vitest unit tests for wizard-state.ts.
// Zero browser APIs, zero React — runs in a plain Node environment.
import { describe, expect, it } from "vitest";
import {
  canAdvanceTo,
  getNextStep,
  getPrevStep,
  isStepComplete,
  isValidStep,
  STEP_ORDER,
  type WizardProjectState,
} from "./wizard-state";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const emptyProject: WizardProjectState = {
  wizard_step: "upload",
  voice_profile_id: null,
  slide_count: 0,
  script_count: 0,
  audio_clip_count: 0,
  has_video_artifact: false,
};

const withSlides: WizardProjectState = {
  ...emptyProject,
  slide_count: 3,
};

const withVoice: WizardProjectState = {
  ...withSlides,
  voice_profile_id: "00000000-0000-0000-0000-000000000001",
};

const withScripts: WizardProjectState = {
  ...withVoice,
  script_count: 3,
};

const withAudio: WizardProjectState = {
  ...withScripts,
  audio_clip_count: 3,
};

const withVideo: WizardProjectState = {
  ...withAudio,
  has_video_artifact: true,
};

// ---------------------------------------------------------------------------
// getNextStep
// ---------------------------------------------------------------------------

describe("getNextStep", () => {
  it("upload → voice", () => {
    expect(getNextStep("upload")).toBe("voice");
  });
  it("voice → scripts", () => {
    expect(getNextStep("voice")).toBe("scripts");
  });
  it("scripts → audio", () => {
    expect(getNextStep("scripts")).toBe("audio");
  });
  it("audio → render", () => {
    expect(getNextStep("audio")).toBe("render");
  });
  it("render → done", () => {
    expect(getNextStep("render")).toBe("done");
  });
  it("done → null (last step)", () => {
    expect(getNextStep("done")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// getPrevStep
// ---------------------------------------------------------------------------

describe("getPrevStep", () => {
  it("upload → null (first step)", () => {
    expect(getPrevStep("upload")).toBeNull();
  });
  it("voice → upload", () => {
    expect(getPrevStep("voice")).toBe("upload");
  });
  it("done → render", () => {
    expect(getPrevStep("done")).toBe("render");
  });
  it("render → audio", () => {
    expect(getPrevStep("render")).toBe("audio");
  });
});

// ---------------------------------------------------------------------------
// canAdvanceTo
// ---------------------------------------------------------------------------

describe("canAdvanceTo — upload", () => {
  it("is always accessible", () => {
    expect(canAdvanceTo("upload", emptyProject)).toBe(true);
    expect(canAdvanceTo("upload", withVideo)).toBe(true);
  });
});

describe("canAdvanceTo — voice", () => {
  it("blocked when no slides", () => {
    expect(canAdvanceTo("voice", emptyProject)).toBe(false);
  });
  it("allowed when slides exist", () => {
    expect(canAdvanceTo("voice", withSlides)).toBe(true);
  });
});

describe("canAdvanceTo — scripts", () => {
  it("blocked when no voice_profile_id", () => {
    expect(canAdvanceTo("scripts", withSlides)).toBe(false);
  });
  it("allowed when voice_profile_id set", () => {
    expect(canAdvanceTo("scripts", withVoice)).toBe(true);
  });
});

describe("canAdvanceTo — audio", () => {
  it("blocked when scripts < slides", () => {
    expect(
      canAdvanceTo("audio", { ...withVoice, script_count: 1 })
    ).toBe(false);
  });
  it("allowed when scripts === slides", () => {
    expect(canAdvanceTo("audio", withScripts)).toBe(true);
  });
  it("blocked when no slides", () => {
    expect(
      canAdvanceTo("audio", { ...withVoice, slide_count: 0, script_count: 0 })
    ).toBe(false);
  });
});

describe("canAdvanceTo — render", () => {
  it("blocked when audio clips < slides", () => {
    expect(
      canAdvanceTo("render", { ...withScripts, audio_clip_count: 2 })
    ).toBe(false);
  });
  it("allowed when audio_clip_count === slide_count", () => {
    expect(canAdvanceTo("render", withAudio)).toBe(true);
  });
});

describe("canAdvanceTo — done", () => {
  it("blocked when no video artifact", () => {
    expect(canAdvanceTo("done", withAudio)).toBe(false);
  });
  it("allowed when video artifact exists", () => {
    expect(canAdvanceTo("done", withVideo)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// isStepComplete
// ---------------------------------------------------------------------------

describe("isStepComplete", () => {
  it("upload: false when no slides", () => {
    expect(isStepComplete("upload", emptyProject)).toBe(false);
  });
  it("upload: true when slides exist", () => {
    expect(isStepComplete("upload", withSlides)).toBe(true);
  });
  it("voice: false when no voice_profile_id", () => {
    expect(isStepComplete("voice", withSlides)).toBe(false);
  });
  it("voice: true when voice_profile_id set", () => {
    expect(isStepComplete("voice", withVoice)).toBe(true);
  });
  it("scripts: false when scripts < slides", () => {
    expect(isStepComplete("scripts", withVoice)).toBe(false);
  });
  it("scripts: true when all scripted", () => {
    expect(isStepComplete("scripts", withScripts)).toBe(true);
  });
  it("audio: false when audio < slides", () => {
    expect(isStepComplete("audio", withScripts)).toBe(false);
  });
  it("audio: true when all audio clips present", () => {
    expect(isStepComplete("audio", withAudio)).toBe(true);
  });
  it("render: false when no video", () => {
    expect(isStepComplete("render", withAudio)).toBe(false);
  });
  it("render: true when video exists", () => {
    expect(isStepComplete("render", withVideo)).toBe(true);
  });
  it("done: mirrors render completion", () => {
    expect(isStepComplete("done", withVideo)).toBe(true);
    expect(isStepComplete("done", withAudio)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isValidStep
// ---------------------------------------------------------------------------

describe("isValidStep", () => {
  it("accepts valid step strings", () => {
    for (const s of STEP_ORDER) {
      expect(isValidStep(s)).toBe(true);
    }
  });
  it("rejects null", () => {
    expect(isValidStep(null)).toBe(false);
  });
  it("rejects arbitrary strings", () => {
    expect(isValidStep("invalid")).toBe(false);
    expect(isValidStep("Upload")).toBe(false);
    expect(isValidStep("")).toBe(false);
  });
});
