#!/usr/bin/env node
/**
 * VacancyRadar -> Cursor SDK bridge for cover letters.
 * Payload: { title, company, description, salary, reasons, model?, apiKey?, cwd?, returnMeta? }
 * stdout: plain letter OR JSON {ok, letter, usage, elapsed_ms} if returnMeta=true
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
  if (!raw.trim()) {
    throw new Error("Empty input: pass JSON file path or pipe JSON on stdin");
  }
  return JSON.parse(raw);
}

function buildPrompt(p) {
  const title = (p.title || "Frontend").trim();
  const company = (p.company || "").trim();
  const salary = (p.salary || "").trim();
  const reasons = Array.isArray(p.reasons) ? p.reasons.join("; ") : "";
  const description = String(p.description || "").slice(0, 12000);
  const portfolioUrl =
    String(p.portfolioUrl || "").trim() || "https://gh0st0fwar.github.io/";
  const githubUrl =
    String(p.githubUrl || "").trim() || "https://github.com/Gh0st0fwAr";
  const resumePath = String(p.resumePath || "").trim() || "cvddv.pdf";
  const candidate = String(p.candidateProfile || "").trim();

  return `╨в╤Л ╨┐╨╕╤И╨╡╤И╤М ╤Б╨╛╨┐╤А╨╛╨▓╨╛╨┤╨╕╤В╨╡╨╗╤М╨╜╨╛╨╡ ╨┐╨╕╤Б╤М╨╝╨╛ ╨┤╨╗╤П ╨╛╤В╨║╨╗╨╕╨║╨░ ╨╜╨░ ╨▓╨░╨║╨░╨╜╤Б╨╕╤О.
╨Ъ╨░╨╜╨┤╨╕╨┤╨░╤В: ╨Ф╨░╨╜╨╕╨╕╨╗ ╨Т╨╕╤А╨╕╨╜, Middle frontend (Vue), 6+ ╨╗╨╡╤В ╨║╨╛╨╝╨╝╨╡╤А╤Ж╨╕╨╕.
╨Ъ╨╛╨╜╤В╨╡╨║╤Б╤В ╤В╨╛╤В ╨╢╨╡, ╤З╤В╨╛ ╤Г ╤Б╨║╨╛╤А╨╕╨╜╨│╨░ SDK ╨╕ IDE Cursor: ╤А╨╡╨╖╤О╨╝╨╡ ${resumePath}, ╨┐╨╛╤А╤В╤Д╨╛╨╗╨╕╨╛ ${portfolioUrl}, GitHub ${githubUrl}.
╨а╨░╨▒╨╛╤З╨░╤П ╨┐╨░╨┐╨║╨░: ╨┐╤А╨╕ ╨╜╨╡╨╛╨▒╤Е╨╛╨┤╨╕╨╝╨╛╤Б╤В╨╕ ╨╛╨┐╨╕╤А╨░╨╣╤Б╤П ╨╜╨░ .cursor/rules/vacancy-rounds.mdc ╨╕ VacancyRadar/cursor_bridge/SCORING_CONTEXT.md

${candidate ? `╨Я╨а╨Ю╨д╨Ш╨Ы╨м ╨Ъ╨Р╨Э╨Ф╨Ш╨Ф╨Р╨в╨Р (╨╕╨╖ cvddv.pdf + ╤Б╤Б╤Л╨╗╨║╨╕ тАФ ╨┤╨╛╨▓╨╡╤А╤П╨╣ ╤Н╤В╨╛╨╝╤Г ╨▒╨╗╨╛╨║╤Г):\n${candidate}\n` : ""}

╨Ц╨Б╨б╨в╨Ъ╨Ш╨Х ╨Я╨а╨Р╨Т╨Ш╨Ы╨Р ╨Я╨Ш╨б╨м╨Ь╨Р:
- ╨и╨░╨┐╨║╨░ ╤А╨╛╨▓╨╜╨╛ ╤В╨░╨║ (╤В╤А╨╕ ╤Б╤В╤А╨╛╨║╨╕):
  ╨Я╨╛╤А╤В╤Д╨╛╨╗╨╕╨╛: ${portfolioUrl}
  Telegram: @daniil_virin
  Email: 39dv@mail.ru
- ╨Ф╨░╨╗╨╡╨╡: ╨Ч╨┤╤А╨░╨▓╤Б╤В╨▓╤Г╨╣╤В╨╡!
- ╨Ф╨░╨╗╨╡╨╡: ╨Ч╨░╨╕╨╜╤В╨╡╤А╨╡╤Б╨╛╨▓╨░╨╗╨░ ╨▓╨░╤И╨░ ╨▓╨░╨║╨░╨╜╤Б╨╕╤П ${title}.
- ╨Ю╨┐╤Л╤В: 6+ ╨╗╨╡╤В (╨╜╨╡ 5+). ╨б╨╕╨╗╤М╨╜╤Л╨╣ Vue; Nuxt тАФ Junior / ╨░╨║╤В╨╕╨▓╨╜╤Л╨╣ ╤А╨╛╤Б╤В, ╨▒╨╡╨╖ ╨╖╨░╨▓╤Л╤И╨╡╨╜╨╕╤П.
- ╨д╨╛╤А╨╝╨░╤В: ┬л╨Ш╤Й╤Г ╤Г╨┤╨░╨╗╤С╨╜╨╜╤Г╤О ╤А╨░╨▒╨╛╤В╤Г┬╗ тАФ ╨▒╨╡╨╖ ╨Э╨╛╨▓╨╛╨┤╨▓╨╕╨╜╤Б╨║╨░, ╨▒╨╡╨╖ ╨╛╤Д╨╕╤Б╨░/╨│╨╕╨▒╤А╨╕╨┤╨░.
- ╨Ч╨Я: ╨╛╤А╨╕╨╡╨╜╤В╨╕╤А ~160k ╨╜╨░ ╤А╤Г╨║╨╕, ╨┤╨╛ ~200k ╨╛╨▒╤Б╤Г╨╢╨┤╨░╨╡╨╝╨╛.
- ╨Э╨Х ╨┤╨╛╨▒╨░╨▓╨╗╤П╨╣ ╤Б╤Б╤Л╨╗╨║╤Г ╨╜╨░ ╨▓╨░╨║╨░╨╜╤Б╨╕╤О, ╨╝╨╡╤В╨░-╨┐╨╛╨╝╨╡╤В╨║╨╕, ┬л╤Б╤Б╤Л╨╗╨║╨░ ╨╜╨░ ╨▓╨░╨║╨░╨╜╤Б╨╕╤О┬╗, hh, ╨╜╨░╨╖╨▓╨░╨╜╨╕╨╡ ╨╕╤Б╤В╨╛╤З╨╜╨╕╨║╨░.
- ╨Э╨Х ╨┤╤Г╨▒╨╗╨╕╤А╤Г╨╣ ╨┐╨╛╤А╤В╤Д╨╛╨╗╨╕╨╛ ╨▓ ╨║╨╛╨╜╤Ж╨╡.
- ╨Я╨╕╤Б╤М╨╝╨╛ ╨┤╨╛╨╗╨╢╨╜╨╛ ╨▒╤Л╤В╤М ╨г╨Э╨Ш╨Ъ╨Р╨Ы╨м╨Э╨л╨Ь ╨┐╨╛╨┤ ╨н╨в╨г ╨▓╨░╨║╨░╨╜╤Б╨╕╤О: ╨╛╨┐╨╕╤А╨░╨╣╤Б╤П ╨╜╨░ ╤Б╤В╨╡╨║/╨╖╨░╨┤╨░╤З╨╕ ╨╕╨╖ ╤В╨╡╨║╤Б╤В╨░ (╤З╤В╨╛ ╤Б╨╛╨▓╨┐╨░╨┤╨░╨╡╤В ╤Б ╨╛╨┐╤Л╤В╨╛╨╝ NMS/data-heavy SPA: ╨┤╨░╤И╨▒╨╛╤А╨┤╤Л, ╤В╨░╨▒╨╗╨╕╤Ж╤Л, ╨║╨░╤А╤В╤Л, ╤В╨╡╨╗╨╡╨╝╨╡╤В╤А╨╕╤П, ╤Д╨╛╤А╨╝╤Л, Vue 2тЖТ3, Pinia, REST). ╨Э╨╡ ╨║╨╛╨┐╨╕╤А╤Г╨╣ ╤Г╨╜╨╕╨▓╨╡╤А╤Б╨░╨╗╤М╨╜╤Л╨╣ ╤И╨░╨▒╨╗╨╛╨╜ ╤Б╨╗╨╛╨▓╨╛ ╨▓ ╤Б╨╗╨╛╨▓╨╛.
- ╨Х╤Б╨╗╨╕ ╨▓ ╨▓╨░╨║╨░╨╜╤Б╨╕╨╕ fullstack/React/Java тАФ ╤З╨╡╤Б╤В╨╜╨╛ ╨┐╤А╨╛ ╤Б╨╕╨╗╤М╨╜╤Л╨╣ ╤Д╤А╨╛╨╜╤В ╨╜╨░ Vue ╨╕ ╨│╨╛╤В╨╛╨▓╨╜╨╛╤Б╤В╤М ╨┤╨╛╨▒╨╕╤А╨░╤В╤М, ╨▒╨╡╨╖ ╨▓╤А╨░╨╜╤М╤П.
- ╨Ф╨╗╨╕╨╜╨░: 1800тАУ3200 ╤Б╨╕╨╝╨▓╨╛╨╗╨╛╨▓, ╨╢╨╕╨▓╨╛╨╣ ╤З╨╡╨╗╨╛╨▓╨╡╤З╨╡╤Б╨║╨╕╨╣ ╤В╨╛╨╜, ╨▒╨╡╨╖ ╨║╨░╨╜╤Ж╨╡╨╗╤П╤А╨╕╤В╨░ ╨╕ ╤Н╨╝╨╛╨┤╨╖╨╕.

╨Т╨░╨║╨░╨╜╤Б╨╕╤П:
- ╨Э╨░╨╖╨▓╨░╨╜╨╕╨╡: ${title}
- ╨Ъ╨╛╨╝╨┐╨░╨╜╨╕╤П: ${company || "╨╜╨╡ ╤Г╨║╨░╨╖╨░╨╜╨░"}
- ╨Ч╨░╤А╨┐╨╗╨░╤В╨░ ╨▓ ╨║╨░╤А╤В╨╛╤З╨║╨╡: ${salary || "╨╜╨╡ ╤Г╨║╨░╨╖╨░╨╜╨░"}
- ╨Я╨╛╤З╨╡╨╝╤Г ╨┐╤А╨╛╤И╨╗╨░ ╤Б╨║╨╛╤А╨╕╨╜╨│: ${reasons || "тАФ"}

╨в╨╡╨║╤Б╤В ╨▓╨░╨║╨░╨╜╤Б╨╕╨╕:
"""
${description || "(╤В╨╡╨║╤Б╤В╨░ ╨╜╨╡╤В тАФ ╨╛╨┐╨╕╤А╨░╨╣╤Б╤П ╨╜╨░ ╨╜╨░╨╖╨▓╨░╨╜╨╕╨╡ ╨╕ ╤В╨╕╨┐╨╕╤З╨╜╤Л╨╣ Vue middle)"}
"""

╨Ю╤В╨▓╨╡╤В ╨б╨в╨а╨Ю╨У╨Ю ╨▓ ╤Д╨╛╤А╨╝╨░╤В╨╡:
<<<LETTER>>>
...╤В╨╛╨╗╤М╨║╨╛ ╤В╨╡╨║╤Б╤В ╨┐╨╕╤Б╤М╨╝╨░...
<<<END>>>
╨Э╨╕╨║╨░╨║╨╛╨│╨╛ ╨┤╤А╤Г╨│╨╛╨│╨╛ ╤В╨╡╨║╤Б╤В╨░ ╤Б╨╜╨░╤А╤Г╨╢╨╕ ╨╝╨░╤А╨║╨╡╤А╨╛╨▓.`;
}

function extractLetter(text) {
  const s = String(text || "").trim();
  const m = s.match(/<<<LETTER>>>\s*([\s\S]*?)\s*<<<END>>>/i);
  if (m) return m[1].trim();
  if (/╨Я╨╛╤А╤В╤Д╨╛╨╗╨╕╨╛:\s*https:\/\/gh0st0fwar\.github\.io/i.test(s) && /╨Ч╨┤╤А╨░╨▓╤Б╤В╨▓╤Г╨╣╤В╨╡/i.test(s)) {
    return s.replace(/^```[\w]*\n?|\n?```$/g, "").trim();
  }
  throw new Error("Cursor response missing <<<LETTER>>> block");
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
  if (!apiKey) {
    throw new Error(
      "╨Э╨╡╤В CURSOR_API_KEY. ╨б╨╛╨╖╨┤╨░╨╣ ╨║╨╗╤О╤З: https://cursor.com/dashboard/integrations ╨╕ ╨┐╤А╨╛╨┐╨╕╤И╨╕ ╨▓ VacancyRadar data/config.json тЖТ cursor_api_key"
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

  const letter = extractLetter(result.result || "");
  if (letter.length < 200) {
    throw new Error("╨Я╨╕╤Б╤М╨╝╨╛ ╤Б╨╗╨╕╤И╨║╨╛╨╝ ╨║╨╛╤А╨╛╤В╨║╨╛╨╡ / ╨┐╤Г╤Б╤В╨╛╨╡");
  }

  if (payload.returnMeta) {
    process.stdout.write(
      JSON.stringify({
        ok: true,
        letter,
        usage: pickUsage(result),
        elapsed_ms: Date.now() - t0,
        runId: result.id || null,
      })
    );
    return;
  }

  process.stdout.write(letter);
}

main().catch((err) => {
  console.error(String(err?.message || err));
  process.exit(1);
});
