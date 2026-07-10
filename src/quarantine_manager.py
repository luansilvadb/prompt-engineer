#!/usr/bin/env python
import argparse
import sys
import os
import subprocess
import platform
import json
from datetime import datetime, timedelta

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Quarantine Manager for Flaky Tests - Assists in detecting, isolating, and reporting flaky tests."
    )
    parser.add_argument(
        "--detect",
        type=str,
        help="A specific test file or test pattern to run and check for flakiness (e.g., tests/test_heuristic_evaluator.py)."
    )
    parser.add_argument(
        "--test",
        type=str,
        help="Path to the test file (or test ID like path::test_name) to move to quarantine immediately."
    )
    parser.add_argument(
        "--reason",
        type=str,
        default="Inconsistent execution results detected in multiple runs on same commit.",
        help="Description of the inconsistency or failure observed."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of consecutive executions for flakiness detection (default: 5)."
    )
    parser.add_argument(
        "--critical-suites",
        type=str,
        help="Comma-separated file paths or names of critical test suites where quarantine results in unstable status."
    )
    parser.add_argument(
        "--ticket-url",
        type=str,
        help="Custom URL for the created issue/ticket (optional)."
    )
    parser.add_argument(
        "--pr-url",
        type=str,
        help="Custom URL for the PR comment (optional)."
    )
    return parser.parse_args()

def run_pytest_on_target(test_target: str) -> tuple[bool, str]:
    """
    Runs pytest on the specified target.
    Returns a tuple (passed, output) where passed is a boolean.
    """
    cmd = [sys.executable, "-m", "pytest", test_target, "-q"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    passed = (result.returncode == 0)
    output = result.stdout + result.stderr
    return passed, output

def detect_flakiness(test_target: str, max_runs: int = 5) -> tuple[bool, int, int, list[str]]:
    """
    Runs the test target multiple times to check for flaky behavior.
    Returns (is_flaky, pass_count, fail_count, failure_logs).
    """
    results = []
    failure_logs = []

    print(f"[*] Starting flakiness detection on target: '{test_target}' with {max_runs} runs.")
    for run_idx in range(1, max_runs + 1):
        passed, log = run_pytest_on_target(test_target)
        status_str = "PASSED" if passed else "FAILED"
        print(f"    Run {run_idx}/{max_runs}: {status_str}")
        results.append(passed)
        if not passed:
            failure_logs.append(log)

    has_pass = any(results)
    has_fail = not all(results)
    is_flaky = has_pass and has_fail

    pass_count = results.count(True)
    fail_count = results.count(False)

    return is_flaky, pass_count, fail_count, failure_logs

def isolate_file(src_file: str, dest_dir: str, reason: str) -> str:
    """
    Moves src_file to dest_dir and prepends the quarantine comment.
    Returns the path to the moved file.
    """
    os.makedirs(dest_dir, exist_ok=True)
    basename = os.path.basename(src_file)
    dest_file = os.path.join(dest_dir, basename)

    if not os.path.exists(src_file):
        raise FileNotFoundError(f"Source test file not found: {src_file}")

    # Read original content
    with open(src_file, "r", encoding="utf-8") as f:
        content = f.read()

    data_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Exact required format preserving "identado":
    # // QUARENTENA: Teste flaky identado em {DATA}. Razão: {descrição da inconsistência}.
    # Since it's Python, we prepend # so it remains a valid comment
    comment_line = f"# // QUARENTENA: Teste flaky identado em {data_str}. Razão: {reason}.\n"

    new_content = comment_line + content

    with open(dest_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    os.remove(src_file)
    return dest_file

def register_ticket(test_name: str, fail_logs: list[str], custom_url: str = None) -> dict:
    """
    Simulates and records ticket creation metadata.
    """
    try:
        commit_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit_hash = "unknown-commit-hash"

    env_info = f"Python {platform.python_version()} on {platform.system()} ({platform.release()})"

    logs_joined = "\n".join(fail_logs) if fail_logs else "No failure logs captured."
    steps = f"1. Run test locally: python -m pytest {test_name}\n2. Observe intermittent success/failure pattern under identical conditions."

    title = f"[FLAKY-TEST] {test_name}"
    labels = ["flaky", "quarentena", "tech-debt"]

    # Generate mock URL if none provided
    ticket_id = abs(hash(test_name)) % 10000
    url = custom_url or f"https://github.com/mock-org/mock-repo/issues/{ticket_id}"

    ticket = {
        "title": title,
        "labels": labels,
        "commit_hash": commit_hash,
        "environment": env_info,
        "fail_log": logs_joined,
        "reproduction_steps": steps,
        "url": url
    }

    # Save to mock registry file
    registry_dir = "tests/quarantine"
    os.makedirs(registry_dir, exist_ok=True)
    registry_path = os.path.join(registry_dir, "tickets_registry.json")

    tickets_list = []
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as rf:
                tickets_list = json.load(rf)
        except Exception:
            pass

    tickets_list.append(ticket)
    with open(registry_path, "w", encoding="utf-8") as wf:
        json.dump(tickets_list, wf, indent=2, ensure_ascii=False)

    return ticket

def notify_pr(test_name: str, fail_count: int, ticket_url: str, custom_pr_url: str = None) -> tuple[str, str]:
    """
    Generates notification comment for the PR/MR.
    """
    # Required format:
    # ⚠️ Teste {nome} movido para quarentena após {N} falhas intermitentes. Ticket: {link}.
    comment = f"⚠️ Teste {test_name} movido para quarentena após {fail_count} falhas intermitentes. Ticket: {ticket_url}."

    pr_id = abs(hash(test_name)) % 100000
    pr_url = custom_pr_url or f"https://github.com/mock-org/mock-repo/pull/42#issuecomment-{pr_id}"

    # Save mock comment to file for traceability
    registry_dir = "tests/quarantine"
    os.makedirs(registry_dir, exist_ok=True)
    comments_path = os.path.join(registry_dir, "pr_comments.json")

    comments_list = []
    if os.path.exists(comments_path):
        try:
            with open(comments_path, "r", encoding="utf-8") as rf:
                comments_list = json.load(rf)
        except Exception:
            pass

    comments_list.append({"comment": comment, "url": pr_url, "timestamp": datetime.now().isoformat()})
    with open(comments_path, "w", encoding="utf-8") as wf:
        json.dump(comments_list, wf, indent=2, ensure_ascii=False)

    return comment, pr_url

def generate_report(test_name: str, src_path: str, dest_path: str, fail_count: int, ticket_url: str, pr_url: str, ci_status: str) -> str:
    """
    Generates and returns the structured Markdown report exactly matching specifications.
    """
    next_review_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    report = f"""## Relatório de Quarentena
- Teste: {test_name}
- Arquivo movido: {src_path} → {dest_path}
- Falhas registradas: {fail_count} intermitências
- Ticket criado: {ticket_url}
- PR notificado: {pr_url}
- Status do CI: {ci_status}
- Próxima revisão sugerida: {next_review_date}"""
    return report

def main():
    args = parse_arguments()

    target_test = args.test
    is_flaky = False
    fail_count = 1
    failure_logs = []

    # If detection was requested, run it first
    if args.detect:
        detect_target = args.detect
        # If --test is not specified, default to the detected target
        if not target_test:
            target_test = detect_target

        is_flaky, pass_cnt, fail_cnt, logs = detect_flakiness(detect_target, args.runs)
        fail_count = fail_cnt if fail_cnt > 0 else 1
        failure_logs = logs

        if not is_flaky and not args.test:
            print("[-] Detection finished. Test is not flaky. No quarantine actions taken.")
            return 0

    if not target_test:
        print("[!] Error: No test target specified for quarantine (use --test or --detect).")
        return 1

    # Extract actual test file from target_test (e.g., strip ::test_name)
    src_file = target_test.split("::")[0] if "::" in target_test else target_test
    test_name = target_test

    print(f"[*] Quarantining test: {test_name} (File: {src_file})")

    # Step 1: Isolamento
    dest_dir = "tests/quarantine"
    try:
        dest_file = isolate_file(src_file, dest_dir, args.reason)
        print(f"[+] Isolated: {src_file} -> {dest_file}")
    except Exception as e:
        print(f"[!] Error during isolation: {e}")
        return 1

    # Step 2: Registro
    ticket = register_ticket(test_name, failure_logs, args.ticket_url)
    print(f"[+] Ticket registered: '{ticket['title']}' ({ticket['url']})")

    # Step 3: Notificação
    comment, pr_url = notify_pr(test_name, fail_count, ticket['url'], args.pr_url)
    print(f"[+] PR Notification queued: {comment}")

    # Step 4: Bloqueio de CI (Critical suite check)
    is_critical = False
    if args.critical_suites:
        critical_list = [s.strip() for s in args.critical_suites.split(",") if s.strip()]
        for crit in critical_list:
            if crit in src_file:
                is_critical = True
                break

    ci_status = "unstable" if is_critical else "stable"

    # Output expected report
    report = generate_report(test_name, src_file, dest_file, fail_count, ticket['url'], pr_url, ci_status)
    print("\n" + report + "\n")

    return 0

if __name__ == "__main__":
    sys.exit(main())
