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

  return `Ты пишешь сопроводительное письмо для отклика на вакансию.
Кандидат: Даниил Вирин, Middle frontend (Vue), 6+ лет коммерции.
Контекст тот же, что у скоринга SDK и IDE Cursor: резюме ${resumePath}, портфолио ${portfolioUrl}, GitHub ${githubUrl}.
Рабочая папка: при необходимости опирайся на .cursor/rules/vacancy-rounds.mdc и VacancyRadar/cursor_bridge/SCORING_CONTEXT.md

${candidate ? `ПРОФИЛЬ КАНДИДАТА (из cvddv.pdf + ссылки — доверяй этому блоку):\n${candidate}\n` : ""}

ЖЁСТКИЕ ПРАВИЛА ПИСЬМА:
- Шапка ровно так (три строки):
  Портфолио: ${portfolioUrl}
  Telegram: @daniil_virin
  Email: 39dv@mail.ru
- Далее: Здравствуйте!
- Далее: Заинтересовала ваша вакансия ${title}.
- Опыт: 6+ лет (не 5+). Сильный Vue; Nuxt — Junior / активный рост, без завышения.
- Формат: «Ищу удалённую работу» — без Новодвинска, без офиса/гибрида.
- ЗП: ориентир ~160k на руки, до ~200k обсуждаемо.
- НЕ добавляй ссылку на вакансию, мета-пометки, «ссылка на вакансию», hh, название источника.
- НЕ дублируй портфолио в конце.
- Письмо должно быть УНИКАЛЬНЫМ под ЭТУ вакансию: опирайся на стек/задачи из текста (что совпадает с опытом NMS/data-heavy SPA: дашборды, таблицы, карты, телеметрия, формы, Vue 2→3, Pinia, REST). Не копируй универсальный шаблон слово в слово.
- Если в вакансии fullstack/React/Java — честно про сильный фронт на Vue и готовность добирать, без вранья.
- Длина: 1800–3200 символов, живой человеческий тон, без канцелярита и эмодзи.

Вакансия:
- Название: ${title}
- Компания: ${company || "не указана"}
- Зарплата в карточке: ${salary || "не указана"}
- Почему прошла скоринг: ${reasons || "—"}

Текст вакансии:
"""
${description || "(текста нет — опирайся на название и типичный Vue middle)"}
"""

Ответ СТРОГО в формате:
<<<LETTER>>>
...только текст письма...
<<<END>>>
Никакого другого текста снаружи маркеров.`;
}

function extractLetter(text) {
  const s = String(text || "").trim();
  const m = s.match(/<<<LETTER>>>\s*([\s\S]*?)\s*<<<END>>>/i);
  if (m) return m[1].trim();
  if (/Портфолио:\s*https:\/\/gh0st0fwar\.github\.io/i.test(s) && /Здравствуйте/i.test(s)) {
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
      "Нет CURSOR_API_KEY. Создай ключ: https://cursor.com/dashboard/integrations и пропиши в VacancyRadar data/config.json → cursor_api_key"
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
    throw new Error("Письмо слишком короткое / пустое");
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
