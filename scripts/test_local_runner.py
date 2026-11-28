"""Safety regressions for the disposable test runner (no Docker required)."""

import importlib.util
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "local_runner", Path(__file__).with_name("test-local.py")
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TestLocalRunner(unittest.TestCase):
    def test_web_never_creates_a_database(self):
        calls = []
        with (
            patch.object(
                runner, "run", side_effect=lambda args, **kw: calls.append(args)
            ),
            patch("sys.argv", ["test-local.py", "--suite", "web"]),
        ):
            runner.main()
        self.assertFalse(any(c[0] == "docker" for c in calls))
        self.assertIn(["corepack", "pnpm", "install", "--frozen-lockfile"], calls)

    def test_failure_cleans_only_owned_container_and_overrides_business_connections(
        self,
    ):
        owned = "a" * 64
        calls = []
        test_env = {}

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:2] == ["docker", "run"]:
                return owned
            if args[:2] == ["docker", "port"]:
                return "127.0.0.1:54321\n"
            if "verify" in args:
                test_env.update(kwargs["env"])
                raise subprocess.CalledProcessError(1, "maven")

        with (
            patch.object(runner, "run", side_effect=fake_run),
            patch.object(
                runner.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0),
            ),
            patch.object(runner.shutil, "which", return_value="docker"),
            patch.dict(
                os.environ,
                {
                    "WORKFLOW_DB_URL": "do-not-use-business",
                    "WORKFLOW_MIGRATION_DB_URL": "do-not-use-business-migrations",
                    "WORKFLOW_MIGRATION_DB_USERNAME": "business-admin",
                    "WORKFLOW_MIGRATION_DB_PASSWORD": "not-a-real-password",
                    "MAVEN_ARGS": "-Dlive=true",
                    "WORKFLOW_RUN_LOCAL_RAG_AGENT_ACCEPTANCE": "true",
                },
            ),
            patch("sys.argv", ["test-local.py", "--suite", "backend"]),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            runner.main()
        self.assertEqual(calls[-1], ["docker", "rm", "--force", "--volumes", owned])
        self.assertEqual(
            test_env["WORKFLOW_DB_URL"],
            "jdbc:postgresql://127.0.0.1:54321/workflow_tests",
        )
        # Flyway must follow each test's effective spring.datasource, including
        # databases created dynamically by Testcontainers fixtures.
        for key in ("URL", "USERNAME", "PASSWORD"):
            self.assertNotIn("WORKFLOW_MIGRATION_DB_" + key, test_env)
        self.assertIn("/graph_tests", test_env["WORKFLOW_LANGGRAPH_TEST_DATABASE_URL"])
        self.assertNotIn("MAVEN_ARGS", test_env)
        self.assertEqual(test_env["WORKFLOW_RUN_LOCAL_RAG_AGENT_ACCEPTANCE"], "false")
        self.assertEqual(test_env["WORKFLOW_RUN_LOCAL_RAG_ACCEPTANCE"], "false")

    def test_no_cleanup_of_existing_container_when_creation_failed(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            if args[:2] == ["docker", "run"]:
                raise subprocess.CalledProcessError(1, "docker")

        with (
            patch.object(runner, "run", side_effect=fake_run),
            patch("sys.argv", ["test-local.py", "--suite", "backend"]),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            runner.main()
        self.assertFalse(any(c[:2] == ["docker", "rm"] for c in calls))


if __name__ == "__main__":
    unittest.main()
