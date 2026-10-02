import json
import shutil
from pathlib import Path

from trends_pipeline.cli import main


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "synthetic"


def _copy_fixture(destination: Path) -> tuple[Path, Path]:
    destination.mkdir(parents=True)
    input_path = destination / "trends.csv"
    manifest_path = destination / "manifest.yaml"
    shutil.copyfile(FIXTURE_DIR / "trends.csv", input_path)
    shutil.copyfile(FIXTURE_DIR / "manifest.yaml", manifest_path)
    return input_path, manifest_path


def test_validate_cli_reports_success(tmp_path: Path, capsys) -> None:
    input_path, manifest_path = _copy_fixture(tmp_path / "input")
    report_path = tmp_path / "validation.json"

    exit_code = main(
        [
            "validate",
            "--input",
            str(input_path),
            "--manifest",
            str(manifest_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert json.loads(report_path.read_text(encoding="utf-8"))["valid"] is True


def test_run_cli_writes_outputs_and_failure_report(tmp_path: Path, capsys) -> None:
    input_path, manifest_path = _copy_fixture(tmp_path / "input")
    output_dir = tmp_path / "processed"
    report_path = tmp_path / "reports" / "validation.json"

    exit_code = main(
        [
            "run",
            "--input",
            str(input_path),
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "time_series.csv").is_file()
    assert (output_dir / "features.csv").is_file()
    assert json.loads(capsys.readouterr().out)["valid"] is True

    input_path.write_text(input_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    exit_code = main(
        [
            "validate",
            "--input",
            str(input_path),
            "--manifest",
            str(manifest_path),
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 2
    assert "SHA-256 does not match" in capsys.readouterr().err
    assert json.loads(report_path.read_text(encoding="utf-8"))["valid"] is False