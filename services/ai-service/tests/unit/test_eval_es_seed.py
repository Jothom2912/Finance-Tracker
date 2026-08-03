import pytest

from tests.eval.es_cleanup import validate_cleanup_target
from tests.eval.es_seed import validate_eval_index


def test_eval_index_requires_structural_prefix() -> None:
    assert validate_eval_index("eval_transactions") == "eval_transactions"
    with pytest.raises(ValueError, match="live transaction"):
        validate_eval_index("transactions")
    with pytest.raises(ValueError, match="live transaction"):
        validate_eval_index("transactions_v2")
    with pytest.raises(ValueError, match="start with"):
        validate_eval_index("sandbox_transactions")


def test_cleanup_refuses_live_and_eval_aliases() -> None:
    assert validate_cleanup_target("p321_transactions") == "p321_transactions"
    assert validate_cleanup_target("transactions", allow_live=True) == "transactions"
    with pytest.raises(ValueError, match="disposable"):
        validate_cleanup_target("transactions")
    with pytest.raises(ValueError, match="disposable"):
        validate_cleanup_target("eval_transactions")
