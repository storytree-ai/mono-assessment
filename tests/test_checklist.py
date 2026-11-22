import json
from datetime import date
from pathlib import Path

from checklist.__main__ import find, pending
from checklist.criteria import EXCEPTION, SATISFIED, UNABLE
from checklist.engine import run
from checklist.model import NoModel, ReplayModel
from checklist.report import render

APPS = Path(__file__).resolve().parent.parent / "applications"
APP_1, APP_2 = APPS / "app-1001-excavator", APPS / "app-1002-tipper"
AS_OF = date(2026, 11, 22)


def checklist(folder, model=None, **kwargs):
    return run(folder, model or ReplayModel(folder / "model-responses"), AS_OF, **kwargs)


def assert_matches_expected(report, folder):
    expected = json.loads((folder / "expected-report.json").read_text())
    items = {item["criterion"]: item for item in report["items"]}
    assert set(items) == set(expected["items"])
    for key, want in expected["items"].items():
        assert (items[key]["state"], items[key]["reason"]) == (want["state"], want["reason"]), key
        refs = [s["ref"] for s in items[key]["sources"]]
        assert all(ref in refs for ref in want.get("sources", [])), key
    assert report["summary"] == expected["summary"]


def test_application_1_matches_its_expected_report_and_is_audited(tmp_path):
    audit = tmp_path / "audit.jsonl"
    first = checklist(APP_1, audit=audit)
    assert_matches_expected(first, APP_1)
    invoice = next(i for i in first["items"] if i["criterion"] == "dealer_invoice@1")
    assert invoice["annotation"]["finding"] and invoice["annotation"]["recommended_action"]
    financials = next(i for i in first["items"] if i["criterion"] == "financials_two_years@1")
    assert "next week" in financials["annotation"]["finding"] and financials["annotation"]["chase_by"] == "2026-11-27"

    first_line = audit.read_text()
    checklist(APP_1, audit=audit)
    lines = audit.read_text().splitlines()
    assert len(lines) == 2 and audit.read_text().startswith(first_line)
    logged = json.loads(lines[0])
    assert logged["model"] == {"provider": "replay", "name": "claude-opus-5-5", "note": None}
    assert logged["criteria"] == [i["criterion"] for i in first["items"]]


def test_application_2_corrupted_document_is_unable_to_verify_not_missing():
    report = checklist(APP_2)
    assert_matches_expected(report, APP_2)
    statement = next(i for i in report["items"] if i["criterion"] == "bank_statements@1")
    assert "can't be read" in statement["finding"] and statement["action"]
    assert statement["documents"] == ["sharepoint/bank-statement.pdf"]


def test_a_source_that_is_down_is_unavailable_never_missing():
    report = checklist(APP_1, down={"sharepoint"})
    states = {i["criterion"]: (i["state"], i["reason"]) for i in report["items"]}
    for key in ("drivers_licence@1", "dealer_invoice@1", "financials_two_years@1"):
        assert states[key] == (UNABLE, "source unavailable")
    assert states["crm_record@1"] == (SATISFIED, "")
    assert report["sources"]["SharePoint"] == "unavailable"


class ConcernedModel(ReplayModel):
    """Replays application 2, adding a model concern on a satisfied item and on an unverifiable one."""

    def ask(self, task, system, user, schema):
        answer = super().ask(task, system, user, schema)
        if task == "annotate":
            for note in answer["annotations"]:
                if note["criterion"] in ("dealer_invoice@1", "bank_statements@1"):
                    note["concern"], note["concern_sources"] = "A broker note quotes a different price.", ["x.md"]
        return answer


def test_a_model_concern_raises_a_satisfied_item_and_never_clears_one():
    report = checklist(APP_2, ConcernedModel(APP_2 / "model-responses"))
    items = {i["criterion"]: i for i in report["items"]}
    invoice = items["dealer_invoice@1"]
    assert (invoice["state"], invoice["reason"]) == (EXCEPTION, "model concern")
    assert invoice["function"]["state"] == SATISFIED
    assert invoice["concern"]["sources"] == ["x.md"]
    assert items["bank_statements@1"]["state"] == UNABLE


def test_every_application_file_is_labelled_as_generated():
    for file in APPS.rglob("*"):
        if file.is_file():
            head = file.read_bytes()[:200]
            assert b"GENERATED" in head or b"_generated" in head, file


class BrokenModel(ReplayModel):
    def ask(self, task, system, user, schema):
        raise ConnectionError("endpoint refused")


def test_with_the_model_off_structured_items_are_decided_and_the_rest_linked_for_the_analyst():
    for model, note in ((NoModel(), "model switched off"), (BrokenModel(APP_1 / "model-responses"), "endpoint refused")):
        report = checklist(APP_1, model)
        items = {i["criterion"]: i for i in report["items"]}
        assert note in report["model"]["note"]
        assert items["crm_record@1"]["state"] == items["credit_report@1"]["state"] == SATISFIED
        for key in ("drivers_licence@1", "dealer_invoice@1", "financials_two_years@1"):
            assert (items[key]["state"], items[key]["reason"]) == (UNABLE, "model unavailable")
            assert items[key]["documents"]
        assert len(report["documents"]) == 6


def test_the_pending_list_holds_every_application_and_each_opens_by_its_id():
    assert [r["application_id"] for r in pending(APPS)] == ["APP-1001", "APP-1002"]
    assert find("app-1001", APPS) == APP_1 and find("APP-1002", APPS) == APP_2
    assert find("app-9", APPS) is None


def test_every_view_reads_as_rule_state_finding_action_sources_with_technical_details_on_request():
    for report in (checklist(APP_1), checklist(APP_2), checklist(APP_1, NoModel())):
        brief = render(report)
        assert brief.startswith(f"{report['application']['application_id']} · {report['application']['applicant']}")
        assert report["run_id"] not in brief and "@1" not in brief and ".json" not in brief
        for gone in ("GENERATED", "does not approve", "What happened", "Next step", "Promise", "Rule:",
                     "Do not correct", "#"):
            assert gone not in brief, gone
        for item in report["items"]:
            block = brief.split(item["title"] + "\n", 1)[1].split("\n\n", 1)[0]
            labels = [line[2:20].strip() for line in block.splitlines()[1:] if line[2:20].strip()]
            assert block.splitlines()[0].strip() == item["state"].capitalize()
            assert labels == [l for l in ("Finding", "Concern", "Recommended action", "Sources") if l in labels]
        assert brief.endswith("Synthetic data: HarbourLine Finance and its applicants are fictional.")
        detailed = render(report, details=True)
        assert report["run_id"] in detailed and report["model"]["name"] in detailed and "crm_record@1" in detailed
    assert "\033[31m" in render(checklist(APP_1), colour=True) and "\033[" not in render(checklist(APP_1))
