#!/usr/bin/env node
/**
 * VacancyRadar -> Cursor SDK vacancy scoring bridge.
 * Scores by candidate CONTEXT (cvddv.pdf + portfolio + GitHub), not Python point rules.
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

function loadLocalRubric() {
  const p = path.join(__dirname, "SCORING_CONTEXT.md");
  try {
    return fs.readFileSync(p, "utf8").trim();
  } catch {
    return "";
  }
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
  const resumePath = String(p.resumePath || "").trim() || "cvddv.pdf";
  const guidance = String(p.scoringRules || "").trim() || loadLocalRubric();
  const candidate =
    String(p.candidateProfile || "").trim() ||
    `=== CANDIDATE (fallback) ===
Resume: ${resumePath}. Portfolio: ${portfolioUrl} and https://Gh0st0fwAr.github.io/. GitHub: ${githubUrl}.
=== END ===`;

  return `You score job vacancies for Daniil Virin using CONTEXT judgment only.
Do NOT apply a fixed Python-style point table (+20 remote, +25 Vue, etc.).
Decide FIT from resume + portfolio demos + GitHub + vacancy text.
Reply with JSON only.

CANONICAL CONTEXT LINKS:
- Resume file: ${resumePath}
- Portfolio: ${portfolioUrl}
- Portfolio (same): https://Gh0st0fwAr.github.io/
- GitHub: ${githubUrl}
Do not refuse scoring if URLs cannot be fetched — context is already embedded below.

${candidate}

${guidance ? `GUIDANCE:\n${guidance}\n` : ""}

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
If accept=true, score should be >= ${threshold}. reasons: 2-6 short items (RU or EN) about FIT.`;
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

  if (!String(payload.candidateProfile || "").trim()) {
    process.stderr.write(
      "WARN: candidateProfile empty — missing cvddv/portfolio block from Python\n"
    );
  }

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
