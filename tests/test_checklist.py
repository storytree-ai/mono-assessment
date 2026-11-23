import json
import re
import shutil
from datetime import date
from pathlib import Path

import checklist.__main__ as command
from checklist.__main__ import find, main, pending
from checklist import documents
from checklist.criteria import CRITERIA, EXCEPTION, EXTRACTED_INPUTS, SATISFIED, UNABLE
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


def test_1_2_every_criterion_is_keyed_by_name_and_version_and_names_when_it_applies_and_what_it_reads():
    keys = [c.key for c in CRITERIA]
    assert len(keys) == len(set(keys)) and "dealer_invoice@1" in keys
    record = json.loads((APP_1 / "crm/record.json").read_text())
    for criterion in CRITERIA:
        assert re.fullmatch(r"[a-z_]+@[0-9]+", criterion.key), criterion.key
        assert criterion.applies_when.strip() and isinstance(criterion.applies(record), bool), criterion.key
        for path, name in criterion.structured.values():
            assert name in json.loads((APP_1 / path).read_text()), (criterion.key, path, name)
        assert set(criterion.extracted) <= set(EXTRACTED_INPUTS), criterion.key
        assert bool(criterion.extracted) == (criterion.document is not None), criterion.key
    invoice = next(c for c in CRITERIA if c.key == "dealer_invoice@1")
    assert invoice.structured == {"loan_amount": ("crm/record.json", "loan_amount")}
    assert (invoice.extracted, invoice.document) == (("invoice_total",), "dealer-invoice")


def test_1_3_application_1_matches_its_expected_report():
    report = checklist(APP_1)
    assert_matches_expected(report, APP_1)
    financials = next(i for i in report["items"] if i["criterion"] == "financials_two_years@1")
    assert "next week" in financials["annotation"]["finding"] and financials["annotation"]["chase_by"] == "2026-11-27"


def test_2_1_the_crm_record_decides_which_criteria_apply():
    first, second = ({i["criterion"] for i in checklist(app)["items"]} for app in (APP_1, APP_2))
    assert "financials_two_years@1" in first and "bank_statements@1" not in first
    assert "bank_statements@1" in second and "financials_two_years@1" not in second


def test_2_2_replayed_application_1_items_take_their_criterion_functions_state():
    report = checklist(APP_1)
    assert_matches_expected(report, APP_1)
    for item in report["items"]:
        assert (item["state"], item["reason"]) == (item["function"]["state"], item["function"]["reason"]), item["criterion"]


def test_2_6_every_run_appends_one_line_to_the_audit_record(tmp_path):
    audit = tmp_path / "audit.jsonl"
    first = checklist(APP_1, audit=audit)
    first_line = audit.read_text()
    checklist(APP_1, audit=audit)
    lines = audit.read_text().splitlines()
    assert len(lines) == 2 and audit.read_text().startswith(first_line)
    logged = json.loads(lines[0])
    assert logged["model"] == {"provider": "replay", "name": "claude-opus-5-5", "note": None}
    assert logged["criteria"] == [i["criterion"] for i in first["items"]]


def test_1_4_application_2_matches_its_expected_report():
    assert_matches_expected(checklist(APP_2), APP_2)


def test_2_3_an_unreadable_document_is_unable_to_verify_naming_the_file():
    report = checklist(APP_2)
    statement = next(i for i in report["items"] if i["criterion"] == "bank_statements@1")
    assert statement["state"] == UNABLE
    assert "can't be read" in statement["finding"] and statement["action"]
    assert statement["documents"] == ["bank-statement.pdf"]


def test_2_4_a_source_that_is_down_is_unavailable_never_missing():
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


def test_2_5_a_model_concern_raises_a_satisfied_item_and_never_clears_one():
    invoice = next(i for i in checklist(APP_1)["items"] if i["criterion"] == "dealer_invoice@1")
    assert invoice["annotation"]["finding"] and invoice["annotation"]["recommended_action"]

    report = checklist(APP_2, ConcernedModel(APP_2 / "model-responses"))
    items = {i["criterion"]: i for i in report["items"]}
    invoice = items["dealer_invoice@1"]
    assert (invoice["state"], invoice["reason"]) == (EXCEPTION, "model concern")
    assert invoice["function"]["state"] == SATISFIED
    assert invoice["concern"]["sources"] == ["x.md"]
    assert items["bank_statements@1"]["state"] == UNABLE


def test_1_1_every_application_file_and_stored_document_is_labelled_as_generated():
    stored = [documents.STORE / folder / name for folder in ("APP-1001", "APP-1002")
              for held in documents.stored(documents.STORE / folder) if held["origin"]["origin"] == "SharePoint (mocked)"
              for name in (held["file"], held["file"].rsplit(".", 1)[0] + ".origin.json")]
    for file in [*APPS.rglob("*"), *documents.STORE.glob("*/*.extraction.json"), *stored]:
        if file.is_file():
            head = file.read_bytes()[:200]
            assert b"GENERATED" in head or b"_generated" in head, file
    assert len(stored) == 12


def test_an_uploaded_document_with_no_extraction_record_reads_awaiting_extraction(tmp_path):
    shutil.copytree(documents.STORE / "APP-1001", tmp_path / "APP-1001")
    scan = tmp_path / "licence-scan.PDF"
    scan.write_bytes(b"%PDF-1.4 a scan the analyst fetched by hand")
    assert documents.upload(tmp_path / "APP-1001", scan, "drivers-licence", "emailed by the broker") == "drivers-licence-2.pdf"
    held = {h["file"]: h for h in documents.stored(tmp_path / "APP-1001")}
    assert held["drivers-licence-2.pdf"]["origin"]["uploaded_from"] == str(scan)
    assert held["drivers-licence-2.pdf"]["extraction"]["status"] == documents.AWAITING
    licence = next(i for i in checklist(APP_1, store=tmp_path)["items"] if i["criterion"] == "drivers_licence@1")
    assert (licence["state"], licence["reason"], licence["annotation"]) == (UNABLE, documents.AWAITING, None)
    assert "drivers-licence-2.pdf" in licence["finding"] and "drivers-licence-2.pdf" in render(checklist(APP_1, store=tmp_path))


class BrokenModel(ReplayModel):
    def ask(self, task, system, user, schema):
        raise ConnectionError("endpoint refused")


def assert_structured_items_decided_and_the_rest_linked(model, note):
    report = checklist(APP_1, model)
    items = {i["criterion"]: i for i in report["items"]}
    assert note in report["model"]["note"]
    assert items["crm_record@1"]["state"] == items["credit_report@1"]["state"] == SATISFIED
    for key in ("drivers_licence@1", "dealer_invoice@1", "financials_two_years@1"):
        assert (items[key]["state"], items[key]["reason"]) == (UNABLE, "model unavailable")
        assert items[key]["documents"]
    assert len(report["documents"]) == 6


def test_3_1_with_the_model_off_structured_items_are_decided_and_the_rest_linked_for_the_analyst():
    assert_structured_items_decided_and_the_rest_linked(NoModel(), "model switched off")


def test_3_2_a_failing_model_call_degrades_to_the_no_model_report_naming_the_failure():
    assert_structured_items_decided_and_the_rest_linked(BrokenModel(APP_1 / "model-responses"), "endpoint refused")


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


def model_line(capsys, tmp_path, argv):
    main(["app-1001", "--details", "--as-of", "2026-11-22", *argv])
    brief = capsys.readouterr().out
    assert brief.startswith("APP-1001 · ")
    logged = json.loads((tmp_path / "audit/audit.jsonl").read_text().splitlines()[-1])
    return next(line.split()[1:3] for line in brief.splitlines() if line.strip().startswith("Model ")), logged["model"]["provider"]


def test_2_7_the_checklist_command_prints_the_report_with_the_configured_model_unless_model_overrides_it(tmp_path, monkeypatch, capsys):
    config = (command.ROOT / "config.toml").read_text()
    (tmp_path / "config.toml").write_text(config)
    monkeypatch.setattr(command, "ROOT", tmp_path)
    assert model_line(capsys, tmp_path, []) == (["claude-opus-5-5", "(replay)"], "replay")
    assert model_line(capsys, tmp_path, ["--model", "none"]) == (["none", "(none):"], "none")
    (tmp_path / "config.toml").write_text(config.replace('provider = "replay"', 'provider = "none"'))
    assert model_line(capsys, tmp_path, []) == (["none", "(none):"], "none")
    assert len((tmp_path / "audit/audit.jsonl").read_text().splitlines()) == 3
