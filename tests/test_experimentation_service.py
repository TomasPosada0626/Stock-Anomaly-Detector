from analytics.experimentation import ExperimentationService


def test_experimentation_assignment_and_summary(tmp_path) -> None:
    service = ExperimentationService(db_path=str(tmp_path / "analytics.db"))
    service.create_experiment(
        name="pricing_banner",
        feature="dashboard",
        variants=["control", "treatment"],
        hypothesis="Treatment increases conversions",
    )

    first = service.assign_variant("pricing_banner", "alice")
    second = service.assign_variant("pricing_banner", "alice")
    assert first == second

    service.track_conversion("pricing_banner", "alice")
    summary = service.summary("pricing_banner")

    assert not summary.empty
    assert int(summary["exposures"].sum()) >= 1
    assert int(summary["conversions"].sum()) >= 1


def test_experimentation_requires_multiple_variants(tmp_path) -> None:
    service = ExperimentationService(db_path=str(tmp_path / "analytics.db"))
    failed = False
    try:
        service.create_experiment(
            name="bad_experiment",
            feature="dashboard",
            variants=["control"],
            hypothesis="Invalid setup",
        )
    except ValueError:
        failed = True
    assert failed is True
