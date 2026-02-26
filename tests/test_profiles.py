"""Tests for built-in profiles."""

from __future__ import annotations

from dataclasses import fields

import pytest

from git_spreader.models import SpreaderConfig
from git_spreader.profiles import PROFILES, get_profile

VALID_FIELD_NAMES = {f.name for f in fields(SpreaderConfig)}


class TestProfileKeys:
    """Each profile should only use valid SpreaderConfig field names."""

    @pytest.mark.parametrize("name", sorted(PROFILES.keys()))
    def test_profile_has_valid_keys(self, name: str) -> None:
        profile = PROFILES[name]
        invalid = set(profile.keys()) - VALID_FIELD_NAMES
        assert not invalid, f"Profile '{name}' has invalid keys: {invalid}"

    @pytest.mark.parametrize("name", sorted(PROFILES.keys()))
    def test_profile_creates_valid_config(self, name: str) -> None:
        """Profile overrides can be applied to create a valid SpreaderConfig."""
        from dataclasses import asdict

        base = asdict(SpreaderConfig())
        base.update(get_profile(name))
        SpreaderConfig(**base)


class TestGetProfile:
    def test_get_known_profile(self) -> None:
        result = get_profile("side-project")
        assert result["working_hours_start"] == "18:00"
        assert result["working_hours_end"] == "23:00"

    def test_get_unknown_profile_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown profile 'nonexistent'"):
            get_profile("nonexistent")

    def test_get_profile_returns_copy(self) -> None:
        """Mutating the returned dict should not affect the original."""
        result = get_profile("default")
        result["working_hours_start"] = "00:00"
        assert PROFILES["default"]["working_hours_start"] == "09:00"


class TestPrecedence:
    """Profile + CLI override precedence works correctly."""

    def test_cli_overrides_profile(self) -> None:
        from git_spreader.config import load_config

        profile_overrides = get_profile("side-project")
        cli_overrides = {"working_hours_start": "20:00"}
        config = load_config(
            repo_path=None,
            cli_overrides=cli_overrides,
            profile_overrides=profile_overrides,
        )
        # CLI should win over profile
        assert config.working_hours_start == "20:00"
        # Profile should still apply for non-overridden fields
        assert config.working_hours_end == "23:00"

    def test_profile_overrides_defaults(self) -> None:
        from git_spreader.config import load_config

        profile_overrides = get_profile("night-owl")
        config = load_config(
            repo_path=None,
            cli_overrides=None,
            profile_overrides=profile_overrides,
        )
        assert config.working_hours_start == "22:00"
        assert config.working_hours_end == "04:00"
        assert config.late_night_probability == 0.0
