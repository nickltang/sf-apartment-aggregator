from sf_apartment_aggregator.config import load_config


def test_load_config_uses_discord_webhook_from_env(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
poll_interval_minutes: 20
sources:
  - name: craigslist_sf
    type: browser
    url: https://sfbay.craigslist.org/search/sfc/apa
filters:
  max_price: 3500
  min_beds: 1
discord:
  webhook_url:
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/123/abc")
    app_config = load_config(config_path)
    assert str(app_config.discord.strict_webhook_url) == "https://discord.com/api/webhooks/123/abc"


def test_load_config_uses_explicit_stream_webhooks_from_env(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
poll_interval_minutes: 20
sources:
  - name: craigslist_sf
    type: browser
    url: https://sfbay.craigslist.org/search/sfc/apa
filters:
  max_price: 3500
  min_beds: 1
discord: {}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("DISCORD_STRICT_WEBHOOK_URL", "https://discord.com/api/webhooks/strict/abc")
    monkeypatch.setenv("DISCORD_BROAD_WEBHOOK_URL", "https://discord.com/api/webhooks/broad/xyz")
    app_config = load_config(config_path)
    assert str(app_config.discord.strict_webhook_url) == "https://discord.com/api/webhooks/strict/abc"
    assert str(app_config.discord.broad_webhook_url) == "https://discord.com/api/webhooks/broad/xyz"


def test_load_config_reads_repo_dotenv_when_shell_env_missing(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    dotenv_path = tmp_path / ".env"
    config_path.write_text(
        """
poll_interval_minutes: 20
sources:
  - name: craigslist_sf
    type: browser
    url: https://sfbay.craigslist.org/search/sfc/apa
filters:
  max_price: 3500
  min_beds: 1
discord: {}
""".strip(),
        encoding="utf-8",
    )
    dotenv_path.write_text(
        "DISCORD_STRICT_WEBHOOK_URL=https://discord.com/api/webhooks/from-dotenv/abc\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("DISCORD_STRICT_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("DISCORD_BROAD_WEBHOOK_URL", raising=False)

    app_config = load_config(config_path)

    assert str(app_config.discord.strict_webhook_url) == "https://discord.com/api/webhooks/from-dotenv/abc"
