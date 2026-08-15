#!/usr/bin/env node
/**
 * VacancyRadar → Cursor SDK bridge.
 * stdin/argv JSON: { title, company, description, salary, reasons, model?, apiKey?, cwd? }
 * stdout: plain cover letter text
 * exit 0 on success, non-zero on failure (stderr = reason)
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
  const description = String(p.description || "").slice(0, 7000);

  return `Ты пишешь сопроводительное письмо для отклика на вакансию.
Кандидат: Даниил Вирин, Middle frontend (Vue), 6+ лет коммерции.
Рабочая папка с правилами: прочитай при необходимости .cursor/rules/vacancy-rounds.mdc

ЖЁСТКИЕ ПРАВИЛА ПИСЬМА:
- Шапка ровно так (три строки):
  Портфолио: https://gh0st0fwar.github.io/
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
  // fallback: whole response if it looks like a letter
  if (/Портфолио:\s*https:\/\/gh0st0fwar\.github\.io/i.test(s) && /Здравствуйте/i.test(s)) {
    return s.replace(/^```[\w]*\n?|\n?```$/g, "").trim();
  }
  throw new Error("Cursor response missing <<<LETTER>>> block");
}

async function main() {
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
    path.resolve(__dirname, "..", "..") || // G:\Лёха уроки
    process.cwd();

  const modelId = payload.model || "composer-2.5";
  const result = await Agent.prompt(buildPrompt(payload), {
    apiKey,
    model: { id: modelId },
    // Только текст — без правок файлов / shell
    tools: [],
    local: { cwd },
  });

  if (result.status === "error") {
    throw new Error(result.error?.message || `Cursor run error (${result.id})`);
  }

  const letter = extractLetter(result.result || "");
  if (letter.length < 200) {
    throw new Error("Письмо слишком короткое / пустое");
  }
  process.stdout.write(letter);
}

main().catch((err) => {
  console.error(String(err?.message || err));
  process.exit(1);
});
