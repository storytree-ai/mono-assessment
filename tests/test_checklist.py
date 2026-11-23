import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from checklist import __main__ as cli
from checklist.__main__ import find, pending
from checklist import cache
from checklist.connectors import SHAREPOINT
from checklist.criteria import EXCEPTION, SATISFIED, UNABLE
from checklist.engine import run
from checklist.model import NoModel, ReplayModel
from checklist.report import render

APPS = Path(__file__).resolve().parent.parent / "applications"
APP_1, APP_2 = APPS / "app-1001-excavator", APPS / "app-1002-tipper"
AS_OF = date(2026, 11, 22)


@pytest.fixture(autouse=True)
def local_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE", tmp_path / "cache")
    return tmp_path / "cache"


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


def test_the_document_parsers_own_error_passes_up_into_the_finding():
    report = checklist(APP_2)
    statement = next(i for i in report["items"] if i["criterion"] == "bank_statements@1")
    assert (statement["state"], statement["reason"]) == (UNABLE, "unreadable")
    assert "bank-statement.pdf (the file is not a readable PDF) can't be read." in render(report)


def test_an_error_no_layer_turned_into_a_status_reaches_the_analyst_as_a_plain_system_error(monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise KeyError("crm_record")

    monkeypatch.setattr(cli, "run", broken)
    for argv, raw in ((["app-1001"], False), (["app-1001", "--details"], True)):
        with pytest.raises(SystemExit) as stopped:
            cli.main(argv)
        assert stopped.value.code != 0
        said = capsys.readouterr()
        assert "could not be built: a system error, not a finding about this application" in said.err
        assert "Traceback" not in said.err + said.out and ("crm_record" in said.err) == raw


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


class MisquotingModel(ReplayModel):
    def ask(self, task, system, user, schema):
        answer = super().ask(task, system, user, schema)
        for i in answer.get("inputs", []):
            if i["criterion"] == "drivers_licence@1":
                i["quote"] = "Expiry: 30 SEP 2028"
        return answer


def test_a_model_quote_not_found_in_its_source_document_is_unable_to_verify():
    items = {i["criterion"]: i for i in checklist(APP_1, MisquotingModel(APP_1 / "model-responses"))["items"]}
    licence = items["drivers_licence@1"]
    assert (licence["state"], licence["reason"]) == (UNABLE, "please check")
    assert "isn't in drivers-licence.pdf" in licence["finding"]
    assert items["dealer_invoice@1"]["state"] == EXCEPTION


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


def test_1_1_every_application_file_and_mocked_sharepoint_document_is_labelled_as_generated():
    files = [f for f in (*APPS.rglob("*"), *SHAREPOINT.rglob("*")) if f.is_file()]
    for file in files:
        head = file.read_bytes()[:200]
        assert b"GENERATED" in head or b"_generated" in head, file
    assert len([f for f in files if f.suffix == ".pdf"]) == 6


def test_a_run_stamps_everything_it_caches_with_its_id_and_the_audit_names_it(local_cache, tmp_path):
    report = checklist(APP_1, audit=tmp_path / "audit.jsonl")
    held = cache.held(local_cache / "APP-1001")
    assert len(held) == 6 and {e["origin"]["run_id"] for e in held} == {report["run_id"]}
    assert json.loads((tmp_path / "audit.jsonl").read_text())["run_id"] == report["run_id"]


def test_a_stale_document_from_another_run_reads_unavailable(local_cache):
    earlier = checklist(APP_1)
    report = checklist(APP_1, down={"sharepoint"})
    stale = [e for e in cache.held(local_cache / "APP-1001") if e["origin"]["run_id"] == earlier["run_id"]]
    assert {e["path"] for e in stale} == {"dealer-invoice.pdf", "drivers-licence.pdf", "financials-fy2025.pdf"}
    licence = next(i for i in report["items"] if i["criterion"] == "drivers_licence@1")
    assert (licence["state"], licence["reason"], licence["documents"]) == (UNABLE, "source unavailable", [])
    assert not any(d["source"] == "SharePoint" for d in report["documents"])


def test_twist_4_an_upload_in_the_run_is_read_while_sharepoint_is_down(local_cache, tmp_path):
    scan = tmp_path / "licence-scan.PDF"
    scan.write_bytes(b"%PDF-1.4 a scan the analyst fetched by hand")
    offered = []

    def offer(docs):
        offered.extend(d.path for d in docs)
        return [(scan, "drivers-licence", "emailed by the broker")]

    report = checklist(APP_1, down={"sharepoint"}, offer_upload=offer)
    assert offered == ["crm/credit-report.json", "crm/record.json", "email/broker-2026-11-18.md"]
    items = {i["criterion"]: i for i in report["items"]}
    licence = items["drivers_licence@1"]
    assert (licence["state"], licence["reason"], licence["annotation"]) == (UNABLE, "document parser unavailable", None)
    assert licence["documents"] == ["drivers-licence.pdf"] and "drivers-licence.pdf" in render(report)
    invoice = items["dealer_invoice@1"]
    assert (invoice["state"], invoice["reason"], invoice["annotation"]) == (UNABLE, "source unavailable", None)
    upload = next(e for e in cache.held(local_cache / "APP-1001") if e["path"] == "drivers-licence.pdf")
    assert upload["origin"]["run_id"] == report["run_id"] and upload["origin"]["uploaded_from"] == str(scan)


def test_cache_entries_older_than_the_retention_period_are_dropped_at_the_start_of_a_run(local_cache):
    checklist(APP_1)
    origin_file = local_cache / "APP-1001" / "documents" / "dealer-invoice.origin.json"
    origin = json.loads(origin_file.read_text())
    origin["cached_at"] = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    origin_file.write_text(json.dumps(origin))
    checklist(APP_1, retention_days=14, down={"sharepoint"})
    paths = {e["path"] for e in cache.held(local_cache / "APP-1001")}
    assert "dealer-invoice.pdf" not in paths and "drivers-licence.pdf" in paths
    assert not (local_cache / "APP-1001" / "documents" / "dealer-invoice.pdf").exists()


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
