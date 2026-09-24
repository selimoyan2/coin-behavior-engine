"""Unit tests for the web monitoring server."""

from coin_behavior_engine.web.server import get_engine_state, render_dashboard_html


def test_get_engine_state():
    state = get_engine_state()
    assert state["engine"] == "Coin Behavior Engine"
    assert state["model_version"] == "CBE-0.7.0"
    assert state["model_status"] == "FROZEN"
    assert "phases" in state
    assert state["phases"]["phase_a"]["status"] == "COMPLETE"
    assert state["phases"]["phase_b"]["status"] == "IN_PROGRESS"
    assert state["integrity"]["lockbox_verified"] is True
    assert state["integrity"]["lookahead_breaches"] == 0


def test_render_dashboard_html():
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "<!DOCTYPE html>" in html
    assert "Coin Behavior Engine" in html
    assert "CBE-0.7.0" in html
    assert "MODEL FROZEN" in html
    assert "/health" in html
