from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_annual_report_upload_and_message_limits_are_aligned():
    with (ROOT / ".streamlit" / "config.toml").open("rb") as config_file:
        config = tomllib.load(config_file)

    server = config["server"]
    assert server["maxUploadSize"] == 100
    assert server["maxMessageSize"] == 100
