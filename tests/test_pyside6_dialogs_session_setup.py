"""Phase 3c-ii pass 3 — gui_qt.dialogs.session_setup tests.

Pure validators tested without Qt; dialog construction + return-
value tests with pytest-qt.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from gui_qt.dialogs.session_setup import (
    MovieSessionSetup,
    TVSessionSetup,
    _MovieFields,
    _MovieSetupDialog,
    _TVFields,
    _TVSetupDialog,
    ask_movie_setup,
    ask_tv_setup,
    validate_movie_fields,
    validate_tv_fields,
)


# ==========================================================================
# Pure validators
# ==========================================================================


def _movie(**overrides):
    base = dict(
        title="Inception",
        year="2010",
        edition="",
        metadata_provider="TMDB",
        metadata_id="",
        replace_existing=False,
        keep_raw=False,
        extras_mode="ask",
    )
    base.update(overrides)
    return _MovieFields(**base)


def _tv(**overrides):
    base = dict(
        title="Breaking Bad",
        year="2008",
        season="1",
        starting_disc="1",
        episode_mapping="auto",
        metadata_provider="TMDB",
        metadata_id="",
        multi_episode="auto",
        specials="ask",
        replace_existing=False,
        keep_raw=False,
    )
    base.update(overrides)
    return _TVFields(**base)


def test_validate_movie_happy_path():
    assert validate_movie_fields(_movie()) is None


def test_validate_movie_empty_title_rejected():
    err = validate_movie_fields(_movie(title=""))
    assert err is not None
    assert "title" in err.lower()


def test_validate_movie_whitespace_title_rejected():
    err = validate_movie_fields(_movie(title="   "))
    assert err is not None


def test_validate_movie_blank_year_accepted():
    """Year is optional — blank doesn't fail validation."""
    assert validate_movie_fields(_movie(year="")) is None


def test_validate_movie_non_numeric_year_rejected():
    err = validate_movie_fields(_movie(year="last year"))
    assert err is not None
    assert "year" in err.lower()


def test_validate_movie_year_out_of_range_rejected():
    err = validate_movie_fields(_movie(year="3000"))
    assert err is not None


def test_validate_movie_unknown_provider_rejected():
    err = validate_movie_fields(_movie(metadata_provider="MyMetadata"))
    assert err is not None
    assert "provider" in err.lower()


def test_validate_movie_unknown_extras_mode_rejected():
    err = validate_movie_fields(_movie(extras_mode="weird"))
    assert err is not None


def test_validate_tv_happy_path():
    assert validate_tv_fields(_tv()) is None


def test_validate_tv_season_zero_accepted():
    """Season 0 is valid (specials season)."""
    assert validate_tv_fields(_tv(season="0")) is None


def test_validate_tv_negative_season_rejected():
    err = validate_tv_fields(_tv(season="-1"))
    assert err is not None


def test_validate_tv_non_numeric_season_rejected():
    err = validate_tv_fields(_tv(season="one"))
    assert err is not None


def test_validate_tv_starting_disc_zero_rejected():
    """Starting disc must be ≥ 1."""
    err = validate_tv_fields(_tv(starting_disc="0"))
    assert err is not None


def test_validate_tv_unknown_episode_mapping_rejected():
    err = validate_tv_fields(_tv(episode_mapping="hand-rolled"))
    assert err is not None


def test_validate_tv_unknown_multi_episode_rejected():
    err = validate_tv_fields(_tv(multi_episode="???"))
    assert err is not None


def test_validate_tv_unknown_specials_rejected():
    err = validate_tv_fields(_tv(specials="elsewhere"))
    assert err is not None


# ==========================================================================
# Movie dialog
# ==========================================================================


def test_movie_dialog_chrome(qtbot):
    d = _MovieSetupDialog(
        default_title="Inception", default_year="2010",
        default_metadata_provider="TMDB", default_metadata_id="",
    )
    qtbot.addWidget(d)
    assert d.windowTitle() == "Movie — Library Identity"
    assert d.objectName() == "movieSetupDialog"
    assert d.isModal()


def test_movie_dialog_default_values_propagate(qtbot):
    d = _MovieSetupDialog(
        default_title="Dune", default_year="2021",
        default_metadata_provider="OpenDB", default_metadata_id="tt12345",
    )
    qtbot.addWidget(d)
    assert d._title_edit.text() == "Dune"
    assert d._year_edit.text() == "2021"
    assert d._meta_provider_combo.currentText() == "OpenDB"
    assert d._meta_id_edit.text() == "tt12345"


def test_movie_dialog_ok_returns_setup_dataclass(qtbot):
    d = _MovieSetupDialog(
        default_title="Dune", default_year="2021",
        default_metadata_provider="TMDB", default_metadata_id="",
    )
    qtbot.addWidget(d)
    d._on_ok()
    assert isinstance(d.result_value, MovieSessionSetup)
    assert d.result_value.title == "Dune"
    assert d.result_value.year == "2021"


def test_movie_dialog_cancel_returns_none(qtbot):
    d = _MovieSetupDialog(
        default_title="Dune", default_year="2021",
        default_metadata_provider="TMDB", default_metadata_id="",
    )
    qtbot.addWidget(d)
    d._on_cancel()
    assert d.result_value is None


def test_movie_dialog_ok_with_invalid_title_shows_error(qtbot):
    """Empty title → error label shown, result not set."""
    d = _MovieSetupDialog(
        default_title="", default_year="",
        default_metadata_provider="TMDB", default_metadata_id="",
    )
    qtbot.addWidget(d)
    d._on_ok()
    assert d.result_value is None
    # Visibility on un-shown dialog is False; check the label has
    # been populated and the dialog wasn't accepted.
    assert d._error_label.text(), "error label should be populated"
    assert "title" in d._error_label.text().lower()


def test_movie_dialog_custom_edition_enables_custom_field(qtbot):
    """Selecting "Custom…" enables the custom-edition entry."""
    d = _MovieSetupDialog(
        default_title="X", default_year="",
        default_metadata_provider="TMDB", default_metadata_id="",
    )
    qtbot.addWidget(d)
    assert not d._edition_custom_edit.isEnabled()
    d._edition_combo.setCurrentText("Custom…")
    assert d._edition_custom_edit.isEnabled()
    d._edition_custom_edit.setText("Final Cut")
    d._on_ok()
    assert d.result_value is not None
    assert d.result_value.edition == "Final Cut"


def test_ask_movie_setup_returns_value(qtbot, monkeypatch):
    """Public function: monkeypatch dialog.exec, simulate OK click."""
    def fake_exec(self):
        self._title_edit.setText("Inception")
        self._on_ok()
        return 1

    monkeypatch.setattr(_MovieSetupDialog, "exec", fake_exec)
    result = ask_movie_setup(None, default_title="Inception", default_year="2010")
    assert isinstance(result, MovieSessionSetup)
    assert result.title == "Inception"


def test_ask_movie_setup_returns_none_on_cancel(qtbot, monkeypatch):
    def fake_exec(self):
        self._on_cancel()
        return 0

    monkeypatch.setattr(_MovieSetupDialog, "exec", fake_exec)
    assert ask_movie_setup(None, default_title="X") is None


# ==========================================================================
# TV dialog
# ==========================================================================


def test_tv_dialog_chrome(qtbot):
    d = _TVSetupDialog(
        default_title="BB", default_year="2008", default_season="1",
        default_starting_disc="1", default_metadata_provider="TMDB",
        default_metadata_id="", default_episode_mapping="auto",
        default_multi_episode="auto", default_specials="ask",
        default_replace_existing=False,
    )
    qtbot.addWidget(d)
    assert d.windowTitle() == "TV — Library Identity"
    assert d.objectName() == "tvSetupDialog"
    assert d.isModal()


def test_tv_dialog_defaults_propagate(qtbot):
    d = _TVSetupDialog(
        default_title="BB", default_year="2008", default_season="3",
        default_starting_disc="2", default_metadata_provider="OpenDB",
        default_metadata_id="tt903747", default_episode_mapping="manual",
        default_multi_episode="split", default_specials="season0",
        default_replace_existing=True,
    )
    qtbot.addWidget(d)
    assert d._title_edit.text() == "BB"
    assert d._season_edit.text() == "3"
    assert d._disc_edit.text() == "2"
    assert d._mapping_combo.currentText() == "manual"
    assert d._multi_combo.currentText() == "split"
    assert d._specials_combo.currentText() == "season0"
    assert d._meta_provider_combo.currentText() == "OpenDB"
    assert d._meta_id_edit.text() == "tt903747"
    assert d._replace_check.isChecked()


def test_tv_dialog_ok_returns_setup_dataclass(qtbot):
    d = _TVSetupDialog(
        default_title="BB", default_year="2008", default_season="3",
        default_starting_disc="2", default_metadata_provider="TMDB",
        default_metadata_id="", default_episode_mapping="auto",
        default_multi_episode="auto", default_specials="ask",
        default_replace_existing=False,
    )
    qtbot.addWidget(d)
    d._on_ok()
    assert isinstance(d.result_value, TVSessionSetup)
    assert d.result_value.title == "BB"
    assert d.result_value.season == 3
    assert d.result_value.starting_disc == 2


def test_tv_dialog_ok_with_invalid_season_shows_error(qtbot):
    d = _TVSetupDialog(
        default_title="X", default_year="", default_season="not-a-number",
        default_starting_disc="1", default_metadata_provider="TMDB",
        default_metadata_id="", default_episode_mapping="auto",
        default_multi_episode="auto", default_specials="ask",
        default_replace_existing=False,
    )
    qtbot.addWidget(d)
    d._on_ok()
    assert d.result_value is None
    assert d._error_label.text(), "error label should be populated"
    assert "season" in d._error_label.text().lower()


def test_tv_dialog_cancel_returns_none(qtbot):
    d = _TVSetupDialog(
        default_title="X", default_year="", default_season="1",
        default_starting_disc="1", default_metadata_provider="TMDB",
        default_metadata_id="", default_episode_mapping="auto",
        default_multi_episode="auto", default_specials="ask",
        default_replace_existing=False,
    )
    qtbot.addWidget(d)
    d._on_cancel()
    assert d.result_value is None


def test_ask_tv_setup_returns_value(qtbot, monkeypatch):
    def fake_exec(self):
        self._on_ok()
        return 1

    monkeypatch.setattr(_TVSetupDialog, "exec", fake_exec)
    result = ask_tv_setup(None, default_title="BB", default_season="3")
    assert isinstance(result, TVSessionSetup)
    assert result.title == "BB"
    assert result.season == 3
