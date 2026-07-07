from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from app.execution.liquidity_models import ExecutionReadiness, OrderRecommendation, OrderSide
from app.execution.order_constraints import ExecutionOrderRequest
from app.execution.reality import evaluate_execution_reality
from tests.test_liquidity import NOW, snapshot


def valid_request():
    return ExecutionOrderRequest(
        side=OrderSide.SELL,
        price=Decimal("100.0"),
        volume=Decimal("1.000"),
        post_only=True,
    )


def test_missing_contract_status_is_degraded():
    report = evaluate_execution_reality(
        snapshot(scale="5"),
        now=NOW,
        contract_active=None,
        order_request=valid_request(),
    )
    assert report.readiness == ExecutionReadiness.DATA_DEGRADED
    assert report.recommendation == OrderRecommendation.NO_ORDER
    assert "CONTRACT_STATUS_UNAVAILABLE" in report.reasons


def test_inactive_contract_is_no_trade():
    report = evaluate_execution_reality(
        snapshot(scale="5"),
        now=NOW,
        contract_active=False,
        order_request=valid_request(),
    )
    assert report.readiness == ExecutionReadiness.NO_TRADE
    assert "CONTRACT_INACTIVE" in report.reasons


def test_stale_snapshot_is_degraded():
    stale = replace(snapshot(scale="5"), received_at=NOW - timedelta(minutes=1))
    report = evaluate_execution_reality(
        stale,
        now=NOW,
        contract_active=True,
        order_request=valid_request(),
    )
    assert report.readiness == ExecutionReadiness.DATA_DEGRADED
    assert "SNAPSHOT_STALE" in report.reasons


def test_thin_book_is_no_trade():
    report = evaluate_execution_reality(
        snapshot(scale="0.01"),
        now=NOW,
        contract_active=True,
        order_request=valid_request(),
    )
    assert report.readiness == ExecutionReadiness.NO_TRADE
    assert report.recommendation == OrderRecommendation.NO_ORDER


def test_invalid_precision_is_no_trade():
    request = ExecutionOrderRequest(
        side=OrderSide.SELL,
        price=Decimal("100.05"),
        volume=Decimal("1.0005"),
    )
    report = evaluate_execution_reality(
        snapshot(scale="5"),
        now=NOW,
        contract_active=True,
        order_request=request,
    )
    assert report.readiness == ExecutionReadiness.NO_TRADE
    assert "PRICE_NOT_ALIGNED_TO_TICK" in report.reasons
    assert "VOLUME_NOT_ALIGNED_TO_TICK" in report.reasons


def test_healthy_evidence_is_executable():
    report = evaluate_execution_reality(
        snapshot(scale="5"),
        now=NOW,
        contract_active=True,
        order_request=valid_request(),
    )
    assert report.readiness == ExecutionReadiness.EXECUTABLE
    assert report.executable is True
    assert report.recommendation == OrderRecommendation.MARKET_ALLOWED
    assert report.reasons == ()
