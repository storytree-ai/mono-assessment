import json
from datetime import date
from pathlib import Path

from checklist.criteria import EXCEPTION, SATISFIED, UNABLE
from checklist.engine import run
from checklist.model import NoModel, ReplayModel

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
        if "promise_source" in want:
            assert items[key]["promise"]["source"] == want["promise_source"]
    assert report["summary"] == expected["summary"]


def test_application_1_matches_its_expected_report_and_is_audited(tmp_path):
    audit = tmp_path / "audit.jsonl"
    first = checklist(APP_1, audit=audit)
    assert_matches_expected(first, APP_1)
    invoice = next(i for i in first["items"] if i["criterion"] == "dealer_invoice@1")
    assert invoice["annotation"]["what_happened"] and invoice["annotation"]["call_to_action"]

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
    assert "check manually" in statement["detail"]
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
