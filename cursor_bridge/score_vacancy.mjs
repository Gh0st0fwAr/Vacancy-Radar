#!/usr/bin/env node
/**
 * VacancyRadar -> Cursor SDK vacancy scoring bridge.
 * Input JSON (argv[2] or stdin) -> stdout JSON score result.
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

function buildPrompt(p) {
  const title = String(p.title || "").trim() || "Vacancy";
  const company = String(p.company || "").trim();
  const salary = String(p.salary || "").trim();
  const schedule = String(p.schedule || "").trim();
  const experience = String(p.experience || "").trim();
  const threshold = Number(p.threshold || 65);
  const description = String(p.description || "").slice(0, 9000);
  const portfolioUrl =
    String(p.portfolioUrl || "").trim() || "https://gh0st0fwar.github.io/";
  const githubUrl =
    String(p.githubUrl || "").trim() || "https://github.com/Gh0st0fwAr";
  const candidate =
    String(p.candidateProfile || "").trim() ||
    `=== CANDIDATE (fallback short) ===
Middle frontend, 6+ years Vue 2/3 + TypeScript. Nuxt Junior. Remote only ~160k.
Resume: cvddv.pdf (authoritative). Do NOT use resume.txt / ??????.txt.
=== END ===`;

  return `You score job vacancies for candidate Daniil Virin. Reply with JSON only.

CANDIDATE LINKS (explicit context — treat as known profile links):
- Portfolio: ${portfolioUrl}
- GitHub: ${githubUrl}
Use these as evidence of direction (Vue demos / repos). Do NOT crawl Portfolio source repo.
Do NOT refuse scoring if you cannot open the URLs.

${candidate}

SCORING RULES:
- Remote required (else accept=false, low score)
- Vue / Vue2 / Vue3 / Nuxt / Fullstack+Vue or Node -> positive
- Nuxt-only roles: accept is allowed if remote + TS/Vue ecosystem fits; do NOT score 0 just because Nuxt is junior-level — use mid scores (55-75) when fit is partial
- Score vacancy FIT against resume (cvddv.pdf) + links + NMS facts above — not "can I fetch portfolio right now"
- Pure React/Angular/Next without Vue -> usually reject

VACANCY:
- Title: ${title}
- Company: ${company || "-"}
- Salary: ${salary || "not specified"}
- Schedule: ${schedule || "-"}
- Experience field: ${experience || "-"}

TEXT:
"""
${description || "(empty)"}
"""

Queue threshold: ${threshold}.
Return ONLY one JSON object (no markdown):
{"score":0-100,"accept":true|false,"reasons":["short reason 1","..."]}
If accept=true, score should be >= ${threshold}. reasons: 2-6 short items (RU or EN).`;
}

function extractJson(text) {
  const s = String(text || "").trim();
  const fence = s.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const body = fence ? fence[1].trim() : s;
  const start = body.indexOf("{");
  const end = body.lastIndexOf("}");
  if (start < 0 || end <= start) throw new Error("No JSON object in Cursor response");
  return JSON.parse(body.slice(start, end + 1));
}

function pickUsage(result) {
  const u = result?.usage;
  if (!u || typeof u !== "object") return null;
  return {
    inputTokens: Number(u.inputTokens || 0),
    outputTokens: Number(u.outputTokens || 0),
    cacheReadTokens: Number(u.cacheReadTokens || 0),
    cacheWriteTokens: Number(u.cacheWriteTokens || 0),
    reasoningTokens: Number(u.reasoningTokens || 0),
    totalTokens: Number(
      u.totalTokens != null
        ? u.totalTokens
        : (u.inputTokens || 0) + (u.outputTokens || 0)
    ),
  };
}

async function main() {
  const t0 = Date.now();
  const payload = readPayload();
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

  const result = await Agent.prompt(buildPrompt(payload), {
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
  let score = Math.max(0, Math.min(100, Math.round(Number(parsed.score) || 0)));
  let accept = Boolean(parsed.accept);
  let reasons = Array.isArray(parsed.reasons)
    ? parsed.reasons.map((r) => String(r).slice(0, 160)).filter(Boolean).slice(0, 8)
    : [];
  if (!reasons.length) reasons = ["cursor-score"];

  const threshold = Number(payload.threshold || 65);
  if (accept && score < threshold) accept = false;

  process.stdout.write(
    JSON.stringify({
      ok: true,
      score,
      accept,
      reasons,
      source: "cursor",
      usage: pickUsage(result),
      elapsed_ms: Date.now() - t0,
      runId: result.id || null,
    })
  );
}

main().catch((err) => {
  const msg = String(err?.message || err);
  process.stderr.write(msg + "\n");
  process.stdout.write(
    JSON.stringify({
      ok: false,
      error: msg,
      score: 0,
      accept: false,
      reasons: ["cursor-error"],
      source: "cursor",
      elapsed_ms: 0,
    })
  );
  process.exit(1);
});
