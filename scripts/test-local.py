"""Run repository tests with an owned, disposable database. Never use a business DSN."""

import argparse
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "workflow-agent-service"
WEB = ROOT / "workflow-agent-web"


def run(args, cwd=ROOT, env=None, capture=False):
    executable = shutil.which(str(args[0]))
    if executable is None:
        raise RuntimeError(f"Missing executable: {args[0]}; see docs/AI-BOOTSTRAP.md")
    command = [executable, *map(str, args[1:])]
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        command = ["cmd.exe", "/d", "/c", *command]
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        text=True,
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite", choices=["all", "backend", "graph", "web"], default="all"
    )
    parser.add_argument(
        "--p17",
        action="store_true",
        help="also run both P-17 contracts on both backends",
    )
    options = parser.parse_args()
    if options.p17 and options.suite == "web":
        parser.error("--p17 requires backend, graph or all")
    run([sys.executable, "scripts/check-release.py"])
    env = os.environ.copy()
    # Real-provider acceptance must be a separate, explicit operation.
    for key in (
        "JAVA_TOOL_OPTIONS",
        "JDK_JAVA_OPTIONS",
        "_JAVA_OPTIONS",
        "JAVA_OPTS",
        "MAVEN_ARGS",
        "MAVEN_OPTS",
        "WORKFLOW_LANGGRAPH_TEST_PG_BIN",
        "WORKFLOW_MIGRATION_DB_URL",
        "WORKFLOW_MIGRATION_DB_USERNAME",
        "WORKFLOW_MIGRATION_DB_PASSWORD",
    ):
        env.pop(key, None)
    env["PYTHONUTF8"] = "1"
    env["WORKFLOW_RUN_LOCAL_RAG_ACCEPTANCE"] = "false"
    env["WORKFLOW_RUN_LOCAL_RAG_AGENT_ACCEPTANCE"] = "false"
    container = None
    name = "workflow-test-" + uuid.uuid4().hex[:12]
    try:
        if options.suite != "web":
            run(["java", "-version"], env=env)
            run(["docker", "info", "--format", "{{.ServerVersion}}"], env=env)
            run(
                [
                    "uv",
                    "sync",
                    "--project",
                    str(SERVICE / "agent-runtime-langgraph"),
                    "--frozen",
                ],
                env=env,
            )
            password = secrets.token_hex(24)
            env.update(POSTGRES_PASSWORD=password, POSTGRES_DB="workflow_tests")
            container = run(
                [
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    name,
                    "--publish",
                    "127.0.0.1::5432",
                    "--env",
                    "POSTGRES_PASSWORD",
                    "--env",
                    "POSTGRES_DB",
                    "pgvector/pgvector:pg18-trixie",
                ],
                env=env,
                capture=True,
            ).strip()
            print(f"Owned test container: {container}", flush=True)
            for _ in range(60):
                result = subprocess.run(
                    [
                        shutil.which("docker"),
                        "exec",
                        container,
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "postgres",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if result.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Owned test database did not become ready")
            port = (
                run(["docker", "port", container, "5432/tcp"], capture=True)
                .strip()
                .rsplit(":", 1)[1]
            )
            run(
                [
                    "docker",
                    "exec",
                    container,
                    "createdb",
                    "-U",
                    "postgres",
                    "graph_tests",
                ]
            )
            env.update(
                WORKFLOW_DB_URL=f"jdbc:postgresql://127.0.0.1:{port}/workflow_tests",
                WORKFLOW_DB_USERNAME="postgres",
                WORKFLOW_DB_PASSWORD=password,
                WORKFLOW_TEST_DATABASE_URL=f"jdbc:postgresql://127.0.0.1:{port}/workflow_tests",
                WORKFLOW_TEST_DATABASE_USER="postgres",
                WORKFLOW_TEST_DATABASE_PASSWORD=password,
                WORKFLOW_LANGGRAPH_JDBC_URL=f"jdbc:postgresql://127.0.0.1:{port}/graph_tests",
                WORKFLOW_LANGGRAPH_JDBC_USER="postgres",
                WORKFLOW_LANGGRAPH_JDBC_PASSWORD=password,
                WORKFLOW_LANGGRAPH_CHECKPOINT_DSN=f"postgresql://postgres:{password}@127.0.0.1:{port}/graph_tests",
                WORKFLOW_LANGGRAPH_TEST_DATABASE_URL=f"postgresql://postgres:{password}@127.0.0.1:{port}/graph_tests",
            )
            run(
                [
                    "uv",
                    "run",
                    "--project",
                    str(SERVICE / "agent-runtime-langgraph"),
                    "python",
                    "-c",
                    (
                        "import os; from workflow_agent_runtime.postgres import initialize_checkpoint_store; "
                        "initialize_checkpoint_store(os.environ['WORKFLOW_LANGGRAPH_CHECKPOINT_DSN'])"
                    ),
                ],
                env=env,
            )
            maven = (
                [str(SERVICE / "mvnw.cmd")]
                if os.name == "nt"
                else ["bash", str(SERVICE / "mvnw")]
            )
            if options.suite in ("all", "backend"):
                run(
                    [*maven, "--batch-mode", "--no-transfer-progress", "verify"],
                    cwd=SERVICE,
                    env=env,
                )
            if options.suite in ("all", "graph"):
                runtime = SERVICE / "agent-runtime-langgraph"
                run(["uv", "run", "ruff", "check", "."], cwd=runtime, env=env)
                run(
                    ["uv", "run", "ruff", "format", "--check", "."],
                    cwd=runtime,
                    env=env,
                )
                run(["uv", "run", "pytest", "-q"], cwd=runtime, env=env)
            if options.p17:
                for evidence in ("false", "true"):
                    run(
                        [
                            *maven,
                            "-pl",
                            "workflow-boot",
                            "-am",
                            "-Dsurefire.failIfNoSpecifiedTests=false",
                            "-Dworkflow.p17.graph=true",
                            "-Dworkflow.p17.evidence=" + evidence,
                            (
                                "-Dtest=P17JointRunTest#scriptedRunsExercisePublishedBindingsAndOutbox,"
                                "P17GraphJointRunTest#graphRunsExercisePublishedBindingsAndOutbox"
                            ),
                            "test",
                        ],
                        cwd=SERVICE,
                        env=env,
                    )
        if options.suite in ("all", "web"):
            run(["corepack", "pnpm", "install", "--frozen-lockfile"], cwd=WEB, env=env)
            run(
                ["corepack", "pnpm", "exec", "playwright", "install", "chromium"],
                cwd=WEB,
                env=env,
            )
            run(["corepack", "pnpm", "check"], cwd=WEB, env=env)
        print(
            "PASS: selected suites completed. Inspect reports for conditional skips; no live-model quality claim."
        )
    finally:
        if container:
            # Only the exact ID returned by this invocation, never a pre-existing named service.
            run(["docker", "rm", "--force", "--volumes", container])


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except (OSError, subprocess.CalledProcessError) as error:
        print(
            f"Test run failed: {type(error).__name__}. See command output and docs/AI-BOOTSTRAP.md.",
            file=sys.stderr,
        )
        sys.exit(1)
