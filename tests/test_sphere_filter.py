# -*- coding: utf-8 -*-
from radar.sphere_filter import (
    build_sphere_prompt_block,
    hard_reject_out_of_sphere,
    normalize_sphere_category,
    title_sphere_gate,
)


def test_normalize_developer():
    assert normalize_sphere_category("Разработчик") == "developer"
    assert normalize_sphere_category("Frontend developer") == "developer"
    assert normalize_sphere_category("QA engineer") == "qa"


def test_reject_sales_for_developer():
    ok, reasons = hard_reject_out_of_sphere(
        "Менеджер по продажам AI-продуктов",
        "",
        sphere="Разработчик",
    )
    assert ok is True
    assert reasons


def test_reject_smm_for_developer():
    ok, _ = hard_reject_out_of_sphere("SMM-менеджер", "", sphere="Разработчик")
    assert ok is True


def test_keep_vue_for_developer():
    ok, _ = hard_reject_out_of_sphere(
        "Frontend-разработчик (Vue 3 / TypeScript)",
        "",
        sphere="Разработчик",
    )
    assert ok is False


def test_empty_sphere_no_reject():
    ok, _ = hard_reject_out_of_sphere("Менеджер по продажам", "", sphere="")
    assert ok is False


def test_sphere_prompt_block():
    text = build_sphere_prompt_block("Разработчик")
    assert "Разработчик" in text
    assert "developer" in text.lower() or "Normalized" in text


def test_rukovoditel_not_matched_as_voditel_developer():
    ok, reasons = hard_reject_out_of_sphere(
        "Руководитель отдела разработки",
        "",
        sphere="Разработчик",
    )
    assert ok is False
    assert not any("водитель" in r for r in reasons)


def test_rukovoditel_otdela_not_voditel_any_sphere():
    ok, reasons = hard_reject_out_of_sphere(
        "Руководитель отдела",
        "",
        sphere="Дизайнер",
    )
    assert ok is False
    assert not any("водитель" in r for r in reasons)


def test_designer_rejects_team_lead_frontend():
    ok, reasons = hard_reject_out_of_sphere(
        "Team Lead Frontend / руководитель разработки",
        "",
        sphere="Дизайнер",
    )
    assert ok is True
    assert reasons
    assert not any("водитель" in r for r in reasons)


def test_designer_accepts_graphic_designer():
    ok, _ = hard_reject_out_of_sphere(
        "Графический дизайнер",
        "",
        sphere="Дизайнер",
    )
    assert ok is False


def test_designer_accepts_marketplace_designer():
    ok, _ = hard_reject_out_of_sphere(
        "Дизайнер маркетплейсов",
        "",
        sphere="Дизайнер",
    )
    assert ok is False


def test_designer_rejects_senior_frontend_dev():
    ok, reasons = hard_reject_out_of_sphere(
        "Senior frontend-разработчик",
        "",
        sphere="Дизайнер",
    )
    assert ok is True
    assert reasons


def test_designer_rejects_golang_developer():
    ok, reasons = hard_reject_out_of_sphere(
        "Golang developer",
        "",
        sphere="Дизайнер",
    )
    assert ok is True
    assert reasons


def test_developer_rejects_sales_manager():
    ok, reasons = hard_reject_out_of_sphere(
        "Sales manager",
        "",
        sphere="Разработчик",
    )
    assert ok is True
    assert reasons


def test_developer_accepts_vue_developer():
    ok, _ = hard_reject_out_of_sphere(
        "Vue developer",
        "",
        sphere="Разработчик",
    )
    assert ok is False


# ---------------------------------------------------------------------------
# title_sphere_gate — three-tier verdict tests
# ---------------------------------------------------------------------------

class TestTitleSphereGate:
    sphere = "Разработчик"

    # --- HARD PASS ---

    def test_pass_frontend_developer(self):
        v, r = title_sphere_gate("Frontend Developer (Vue 3 / TypeScript)", self.sphere)
        assert v == "pass", r

    def test_pass_vibe_coder(self):
        v, r = title_sphere_gate("Вайб-кодер (AI/Python)", self.sphere)
        assert v == "pass", r

    def test_pass_ai_developer(self):
        v, r = title_sphere_gate("AI Developer / ML Engineer", self.sphere)
        assert v == "pass", r

    def test_pass_vue_js_developer(self):
        v, r = title_sphere_gate("Vue.js разработчик", self.sphere)
        assert v == "pass", r

    def test_pass_senior_backend(self):
        v, r = title_sphere_gate("Senior Backend Developer (Python)", self.sphere)
        assert v == "pass", r

    def test_pass_tech_lead(self):
        v, r = title_sphere_gate("Tech Lead (Frontend)", self.sphere)
        assert v == "pass", r

    def test_pass_prompt_engineer(self):
        v, r = title_sphere_gate("Prompt Engineer / AI Разработчик", self.sphere)
        assert v == "pass", r

    # --- HARD REJECT ---

    def test_reject_sales_manager(self):
        v, r = title_sphere_gate("Менеджер по продажам", self.sphere)
        assert v == "reject", r

    def test_reject_account_manager(self):
        v, r = title_sphere_gate("Account Manager (SaaS)", self.sphere)
        assert v == "reject", r

    def test_reject_office_manager(self):
        v, r = title_sphere_gate("Офис-менеджер", self.sphere)
        assert v == "reject", r

    def test_reject_recruiter(self):
        v, r = title_sphere_gate("Рекрутер", self.sphere)
        assert v == "reject", r

    def test_reject_smm(self):
        v, r = title_sphere_gate("SMM-менеджер", self.sphere)
        assert v == "reject", r

    def test_reject_brand_manager(self):
        v, r = title_sphere_gate("Бренд-менеджер", self.sphere)
        assert v == "reject", r

    # --- UNCERTAIN (should NOT be reject, should NOT be pass) ---

    def test_uncertain_product_manager(self):
        v, r = title_sphere_gate("Product Manager", self.sphere)
        assert v == "uncertain", r

    def test_uncertain_project_manager(self):
        v, r = title_sphere_gate("Менеджер проекта", self.sphere)
        assert v == "uncertain", r

    def test_uncertain_bare_rukovoditel(self):
        v, r = title_sphere_gate("Руководитель", self.sphere)
        assert v == "uncertain", r

    def test_uncertain_rukovoditel_napravleniya(self):
        v, r = title_sphere_gate("Руководитель направления", self.sphere)
        assert v == "uncertain", r

    def test_uncertain_scrum_master(self):
        v, r = title_sphere_gate("Scrum Master", self.sphere)
        assert v == "uncertain", r

    def test_uncertain_it_manager(self):
        v, r = title_sphere_gate("IT-менеджер", self.sphere)
        assert v == "uncertain", r

    # --- UNCERTAIN should NOT be REJECTED for dev-head titles ---

    def test_rukovoditel_razrabotki_not_rejected(self):
        v, r = title_sphere_gate("Руководитель разработки", self.sphere)
        # Either pass or uncertain — but never reject
        assert v != "reject", r

    def test_engineering_manager_not_rejected(self):
        v, r = title_sphere_gate("Engineering Manager", self.sphere)
        assert v != "reject", r

    # --- sphere_uncertain_note injected for uncertain ---

    def test_uncertain_prompt_block_has_warning(self):
        from radar.sphere_filter import build_sphere_prompt_block
        v, reasons = title_sphere_gate("Product Manager", self.sphere)
        assert v == "uncertain"
        block = build_sphere_prompt_block(
            self.sphere,
            uncertain_title="Product Manager",
            uncertain_reasons=reasons,
        )
        assert "Product Manager" in block
        assert "ambiguity" in block.lower() or "confirm" in block.lower()

    # --- no sphere → always uncertain/pass, never crash ---

    def test_no_sphere_no_reject(self):
        v, _ = title_sphere_gate("Менеджер по продажам", "")
        assert v != "reject"
