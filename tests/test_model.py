import numpy as np
from models.isolation import fit_iforest, score_iforest


def test_fit_iforest_deterministic():
    """Test IsolationForest produces consistent results with same random_state."""
    X = np.random.RandomState(42).rand(100, 3)
    
    clf1 = fit_iforest(X, contamination=0.05, random_state=42)
    clf2 = fit_iforest(X, contamination=0.05, random_state=42)
    
    scores1, is_out1 = score_iforest(clf1, X)
    scores2, is_out2 = score_iforest(clf2, X)
    
    # Should be identical
    np.testing.assert_array_almost_equal(scores1, scores2)
    np.testing.assert_array_equal(is_out1, is_out2)


def test_score_iforest_returns_correct_shape():
    """Test score_iforest returns arrays of correct shape."""
    X = np.random.RandomState(42).rand(50, 3)
    
    clf = fit_iforest(X, contamination=0.1, random_state=42)
    scores, is_out = score_iforest(clf, X)
    
    assert len(scores) == 50
    assert len(is_out) == 50
    assert is_out.dtype == bool


def test_contamination_affects_anomaly_count():
    """Test higher contamination finds more anomalies."""
    X = np.random.RandomState(42).rand(100, 3)
    
    clf_low = fit_iforest(X, contamination=0.01, random_state=42)
    clf_high = fit_iforest(X, contamination=0.1, random_state=42)
    
    _, is_out_low = score_iforest(clf_low, X)
    _, is_out_high = score_iforest(clf_high, X)
    
    # Higher contamination should find more anomalies
    assert sum(is_out_high) > sum(is_out_low)
