from services.strategy_governance_service import StrategyGovernanceService, StrategyProposal


def test_strategy_governance_submit_and_approve(tmp_path) -> None:
    service = StrategyGovernanceService(db_path=str(tmp_path / "governance.db"))
    proposal_id = service.submit_proposal(
        StrategyProposal(
            strategy_name="Momentum Plus",
            created_by="alice",
            rationale="Uses momentum regime + anomaly filters.",
        )
    )
    assert proposal_id > 0

    proposals = service.list_proposals(status="PENDING")
    assert not proposals.empty

    updated = service.approve_proposal(proposal_id, approved_by="risk_committee")
    assert updated is True

    approved = service.list_proposals(status="APPROVED")
    assert not approved.empty


def test_strategy_governance_reject_and_validation(tmp_path) -> None:
    service = StrategyGovernanceService(db_path=str(tmp_path / "governance.db"))
    proposal_id = service.submit_proposal(
        StrategyProposal(
            strategy_name="Mean Reversion",
            created_by="bob",
            rationale="Contrarian entries on oversold signals.",
        )
    )

    rejected = service.reject_proposal(proposal_id, approved_by="reviewer")
    assert rejected is True

    second_reject = service.reject_proposal(proposal_id, approved_by="reviewer")
    assert second_reject is False
