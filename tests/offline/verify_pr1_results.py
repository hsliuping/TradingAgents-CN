"""Validate the existing PR1 regression and same-input comparison evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE_SHA = "51060a7682cf51810b4bc3a704829438d18cd8dc"
ID_DIGESTS = {
    "regression": "568bfae5f0cae14e186c49eb5a465a04d3d51c2d7a627b4f3b644e3d75e61860",
    "comparison": "9da4d2a5a3b08d9dc685f94402d7159cd32293bf494735d022875d923e1d9984",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_id(nodeid):
    filename, name = nodeid.split("::", 1)
    return filename.replace("\\", "/").rsplit("/", 1)[-1] + "::" + name


def normalize_package(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def expected_packages(candidate):
    packages = {}
    for line in (candidate / "tests/offline/requirements-pr1.txt").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.split("==")
            key = normalize_package(name)
            require(key not in packages, "Duplicate package pin")
            packages[key] = version
    require(len(packages) == 38, "Expected exactly 38 pinned test packages")
    return packages


def git_head(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"],
                                   text=True, encoding="utf-8").strip()


def load_run(directory, candidate, source, packages, count, failures):
    value = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    require(Path(value["source"]).resolve() == source, "Wrong product source")
    for key in ("blocked_transport", "real_model_order_attempts", "wrong_source_calls"):
        require(value[key] == [], f"Offline boundary violation: {key}")
    require({normalize_package(k): v for k, v in value["installed"].items()} == packages,
            "Test environment differs from the exact package pins")
    for filename, expected in value["test_sha256"].items():
        path = (candidate / "tests/unit/app" / filename).resolve()
        require(path.parent == candidate / "tests/unit/app", "Invalid test evidence path")
        require(digest(path) == expected, "Test bytes changed")
    require(digest(candidate / "tests/offline/run_pr1.py") == value["runner_sha256"],
            "Runner bytes changed")
    require(bool(value["executed_product_files"]), "No product bodies executed")
    for filename, expected in value["executed_product_files"].items():
        path = Path(filename).resolve()
        require(path.is_relative_to(source), "Product code came from another source")
        require(digest(path) == expected, "Executed product bytes changed")
    cases = value["cases"]
    require(len(cases) == count and all(c["phase"] == "call" for c in cases),
            "Wrong count or collection/setup/teardown failure")
    indexed = {case_id(c["nodeid"]): c for c in cases}
    require(len(indexed) == count, "Duplicate case identity")
    identity_hash = hashlib.sha256("\n".join(sorted(indexed)).encode()).hexdigest()
    kind = "regression" if count == 95 else "comparison"
    require(identity_hash == ID_DIGESTS[kind], "Original test identities changed")
    require(Counter(c["outcome"] for c in cases) == {
        "passed": count - failures, **({"failed": failures} if failures else {})},
        "Unexpected pass/fail/skip outcomes")
    suites = list(ET.parse(directory / "tests.xml").iter("testsuite"))
    for field, expected in {"tests": count, "failures": failures, "errors": 0, "skipped": 0}.items():
        require(sum(int(s.attrib[field]) for s in suites) == expected, "JUnit totals disagree: " + field)
    xml_cases = list(ET.parse(directory / "tests.xml").iter("testcase"))
    xml_ids = [c.attrib["classname"].rsplit(".", 1)[-1] + ".py::" + c.attrib["name"] for c in xml_cases]
    require(len(xml_ids) == count and set(xml_ids) == set(indexed), "JUnit case identities disagree")
    for case, identity in zip(xml_cases, xml_ids):
        require(bool(case.findall("failure")) == (indexed[identity]["outcome"] == "failed"),
                "JUnit outcome disagrees with case result")
    require(value["pytest_exit_code"] == (1 if failures else 0), "Unexpected pytest exit")
    return value, indexed


def verify(results, candidate, baseline, head_sha):
    require(sys.version_info[:3] == (3, 12, 14), "Expected Python 3.12.14")
    require(re.fullmatch(r"[0-9a-f]{40}", head_sha), "Expected a full candidate SHA")
    require(git_head(candidate) == head_sha, "Candidate checkout does not match requested SHA")
    require(git_head(baseline) == BASE_SHA, "Baseline checkout changed")
    codes = json.loads((results / "process-exit-codes.json").read_text(encoding="utf-8"))
    require(codes == {"regression": 0, "baseline": 1, "patched": 0}, "Unexpected runner process exits")
    packages = expected_packages(candidate)
    regression, regression_cases = load_run(results / "regression", candidate, candidate, packages, 95, 0)
    before, left = load_run(results / "baseline", candidate, baseline, packages, 33, 26)
    after, right = load_run(results / "patched", candidate, candidate, packages, 33, 0)
    require(before["test_sha256"] == after["test_sha256"], "Comparison used different test code")
    require(before["runner_sha256"] == after["runner_sha256"] == regression["runner_sha256"],
            "Comparison used different runners")
    require(left.keys() == right.keys(), "Comparison case identities differ")
    normal_equalities = 0
    for name, old in left.items():
        new = right[name]
        require(old["inputs"] == new["inputs"], "Comparison inputs differ: " + name)
        for record in (old, new):
            checks = record["checks"]
            require(bool(checks) and all(type(v) is bool for v in checks.values()), "Missing business checks")
            require(all(checks.values()) == (record["outcome"] == "passed"), "Checks disagree with outcome")
        if old["outcome"] == "failed":
            require(old["exception_type"] == "BusinessMismatch" and not old["control"],
                    "Baseline failure is not an expected business reproduction")
        else:
            require(old["control"] and new["control"], "Unexpected baseline pass")
            if name.startswith("test_pr1_comparison.py::test_actual_entry_quality_to_web"):
                for source in ("memory", "task", "report"):
                    for field in ("reports", "summary", "recommendation", "confidence_score", "risk_level",
                                  "key_points", "decision", "stock_symbol", "stock_code", "analysis_date"):
                        require(old["observed"]["web"][source].get(field) == new["observed"]["web"][source].get(field),
                                "Normal business result changed: " + field)
                        normal_equalities += 1
    require(normal_equalities == 60, "Normal Web comparison coverage changed")
    return {"status": "passed", "candidate_sha": head_sha, "baseline_sha": BASE_SHA,
            "regression_passed": len(regression_cases), "baseline_business_failures": 26,
            "normal_controls_passed": 7, "patched_comparison_passed": len(right),
            "normal_web_equalities": normal_equalities, "python": sys.version.split()[0],
            "packages": packages, "real_model_order_attempts": 0, "unexpected_transport_attempts": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    results = args.results.resolve()
    results.mkdir(parents=True, exist_ok=True)
    try:
        value = verify(results, args.candidate.resolve(), args.baseline.resolve(), args.head_sha)
    except (ValueError, KeyError, OSError, TypeError, ET.ParseError, subprocess.SubprocessError) as error:
        value = {"status": "failed", "error": str(error)}
    (results / "verification.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    summary = "PR1 offline verification: **" + value["status"] + "**\n\n"
    if value["status"] == "passed":
        summary += ("| Run | Result |\n|---|---|\n| Regression | 95 passed |\n"
                    "| Upstream comparison | 26 expected BusinessMismatch + 7 normal controls |\n"
                    "| PR1 comparison | 33 passed |\n\n"
                    f"Candidate: `{value['candidate_sha']}`\n\nBaseline: `{BASE_SHA}`\n")
    else:
        summary += "Verification failed; see verification.json and the three run logs.\n"
    (results / "summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps(value))
    return 0 if value["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
