from analytics.event_tracker import AnalyticsEvent, EventTracker


def test_event_tracker_tracks_and_lists_events(tmp_path) -> None:
    tracker = EventTracker(db_path=str(tmp_path / "analytics.db"))
    tracker.track(AnalyticsEvent(username="alice", feature="dashboard", event_name="login_success"))
    tracker.track(
        AnalyticsEvent(username="alice", feature="anomalies", event_name="run_anomaly_methods")
    )

    frame = tracker.list_events(limit=10)
    assert len(frame) == 2
    assert "feature" in frame.columns


def test_event_tracker_top_features_and_funnel(tmp_path) -> None:
    tracker = EventTracker(db_path=str(tmp_path / "analytics.db"))
    tracker.track(AnalyticsEvent(username="alice", feature="dashboard", event_name="login_success"))
    tracker.track(
        AnalyticsEvent(username="alice", feature="dashboard", event_name="load_market_data")
    )
    tracker.track(
        AnalyticsEvent(username="alice", feature="anomalies", event_name="run_anomaly_methods")
    )

    top = tracker.top_features(limit=5)
    assert not top.empty
    assert top.iloc[0]["feature"] == "dashboard"

    funnel = tracker.funnel()
    assert funnel["login_success"] >= 1
    assert funnel["load_market_data"] >= 1
    assert funnel["run_anomaly_methods"] >= 1
