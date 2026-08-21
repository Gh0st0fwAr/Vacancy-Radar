#!/usr/bin/env node
/**
 * VacancyRadar -> Cursor SDK profile/preferences analysis bridge.
 *
 * Modes:
 *  - "profile"      — analyze resume + links, return skills/stack/level/suggested_preferences
 *  - "preferences"  — acknowledge current preference buckets, return notes/buckets_echo
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Agent } from "@cursor/sdk";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function readPayload() {
  const argPath = process.argv[2];
  if (argPath && fs.existsSync(argPath)) {
    return JSON.parse(fs.readFileSync(argPath, "utf8"));
  }
  const raw = fs.readFileSync(0, "utf8");
  if (!raw.trim()) throw new Error("Empty input");
  return JSON.parse(raw);
}

function buildProfilePrompt(p) {
  const candidate = String(p.candidateProfile || "").trim();
  const resume = String(p.resumeText || "").trim();
  const portfolio = String(p.portfolioUrl || "").trim() || "(not set)";
  const github = String(p.githubUrl || "").trim() || "(not set)";

  return `You analyze a candidate's profile (resume + links) for job-search scoring calibration.
Return ONLY one JSON object (no markdown fences, no explanation):

{
  "skills": ["skill1", "skill2", ...],
  "stack": ["tech1", "tech2", ...],
  "level": "junior|middle|senior|lead",
  "notes": "short summary of candidate strengths and gaps",
  "suggested_preferences": {
    "desirable": ["keyword1", ...],
    "neutral": ["keyword1", ...],
    "undesirable": ["keyword1", ...],
    "reject": ["keyword1", ...]
  },
  "scoring_signals": [
    {"signal": "description", "how_cursor_weighs": "positive|negative|neutral"}
  ]
}

Rules:
- "skills" = all technical and soft skills you can extract from the resume.
- "stack" = specific technologies/frameworks/languages (e.g. Vue 3, TypeScript, Nuxt, Node.js).
- "level" = estimated seniority based on resume experience.
- "suggested_preferences" = keywords that should guide vacancy scoring:
  - desirable: technologies/roles/conditions the candidate would benefit from
  - neutral: common terms that neither help nor hurt
  - undesirable: technologies the candidate has no experience with or dislikes
  - reject: hard dealbreakers (e.g. on-site only if candidate wants remote)
- "scoring_signals" = key signals a scoring agent should weigh.
- Be concise. Each list should have 5-20 items max.

CANDIDATE:
${candidate || "(empty)"}

RESUME TEXT:
${resume || "(empty)"}

Portfolio: ${portfolio}
GitHub: ${github}`;
}

function buildPreferencesPrompt(p) {
  const candidate = String(p.candidateProfile || "").trim();
  const prefsBlock = String(p.preferencesBlock || "").trim();

  return `You review a candidate's preference keyword buckets for vacancy scoring.
The buckets control how vacancy text is scored. Acknowledge them and provide brief notes.

Return ONLY one JSON object (no markdown fences):

{
  "notes": "brief analysis of whether buckets look reasonable",
  "buckets_echo": {
    "desirable": ["echoed keywords"],
    "neutral": ["echoed keywords"],
    "undesirable": ["echoed keywords"],
    "reject": ["echoed keywords"]
  }
}

${candidate ? `CANDIDATE:\n${candidate}\n` : ""}

CURRENT PREFERENCES:
${prefsBlock || "(empty)"}

Analyze: are the buckets well-calibrated for this candidate? Any suggestions?`;
}

function buildSphereCalibrationPrompt(p) {
  const sphere = String(p.sphere || "").trim();
  return `You help calibrate vacancy title filters for a job-search sphere: «${sphere}»

Return ONLY one JSON object — no markdown fences, no explanation:
{
  "reject": ["keyword1", "keyword2", ...],
  "pass": ["keyword1", "keyword2", ...]
}

"reject" = short keyword phrases (1-4 words) that CLEARLY indicate a vacancy title is NOT a «${sphere}» role.
"pass"   = short keyword phrases (1-4 words) that CLEARLY indicate a vacancy title IS a «${sphere}» role.

Rules:
- Russian and English patterns both OK; prefer the dominant language on hh.ru (Russian).
- Keep each phrase SHORT (1-4 words).
- Generate 10-20 reject patterns and 5-15 pass patterns.
- Be CONSERVATIVE — only list patterns with near-zero false-positive risk.
- Do NOT list patterns that could appear in legitimate «${sphere}» job titles.

Example for sphere «курьер»:
{
  "reject": ["менеджер по продажам", "разработчик", "дизайнер", "бухгалтер", "маркетолог", "рекрутер", "программист", "тестировщик", "системный администратор", "аналитик", "продакт менеджер"],
  "pass": ["курьер", "доставщик", "delivery", "экспедитор", "велокурьер"]
}

Target sphere: «${sphere}»`;
}

function extractJson(text) {
  const s = String(text || "").trim();

  // 1. Try parsing the whole string directly (fastest path, handles clean responses).
  try {
    return JSON.parse(s);
  } catch (_) {}

  // 2. Strip markdown fences if present.
  const fence = s.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const body = fence ? fence[1].trim() : s;

  // 3. Try direct parse of the (possibly de-fenced) body.
  try {
    return JSON.parse(body);
  } catch (_) {}

  // 4. Use depth-tracking to find the end of the FIRST top-level { … }
  //    and parse only that slice. This handles trailing garbage that
  //    `lastIndexOf("}")` would mis-identify as the JSON boundary.
  const start = body.indexOf("{");
  if (start < 0) throw new Error("No JSON object in Cursor response");

  let depth = 0;
  let inStr = false;
  let escape = false;

  for (let i = start; i < body.length; i++) {
    const ch = body[i];
    if (escape) { escape = false; continue; }
    if (ch === "\\" && inStr) { escape = true; continue; }
    if (ch === '"') { inStr = !inStr; continue; }
    if (inStr) continue;
    if (ch === "{") depth++;
    if (ch === "}") {
      depth--;
      if (depth === 0) {
        return JSON.parse(body.slice(start, i + 1));
      }
    }
  }

  throw new Error("No complete JSON object found in Cursor response");
}

async function main() {
  const t0 = Date.now();
  const payload = readPayload();
  const mode = String(payload.mode || "profile").trim();
  const apiKey =
    payload.apiKey ||
    process.env.CURSOR_API_KEY ||
    process.env.CURSOR_API_KEY_ALT ||
    "";
  if (!apiKey) throw new Error("No CURSOR_API_KEY / cursor_api_key");

  const cwd =
    payload.cwd ||
    path.resolve(__dirname, "..", "..") ||
    process.cwd();
  const modelId = payload.model || "composer-2.5";

  const prompt =
    mode === "preferences"
      ? buildPreferencesPrompt(payload)
      : mode === "sphere_calibration"
      ? buildSphereCalibrationPrompt(payload)
      : buildProfilePrompt(payload);

  const result = await Agent.prompt(prompt, {
    apiKey,
    model: { id: modelId },
    tools: [],
    local: {
      cwd,
      sandboxOptions: { enabled: false },
    },
  });

  if (result.status === "error") {
    throw new Error(result.error?.message || `Cursor run error (${result.id})`);
  }

  const parsed = extractJson(result.result || "");
  parsed.ok = true;
  parsed.mode = mode;
  parsed.elapsed_ms = Date.now() - t0;
  parsed.runId = result.id || null;

  process.stdout.write(JSON.stringify(parsed));
}

main().catch((err) => {
  const msg = String(err?.message || err);
  process.stderr.write(msg + "\n");
  process.stdout.write(
    JSON.stringify({
      ok: false,
      error: msg,
      mode: "unknown",
      elapsed_ms: 0,
    })
  );
  process.exit(1);
});
