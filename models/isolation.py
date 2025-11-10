# models/isolation.py
from sklearn.ensemble import IsolationForest
import numpy as np

def fit_iforest(X, contamination=0.05, random_state=42):
    """
    Fit an IsolationForest on feature matrix X (numpy array of shape [n_samples, n_features]).
    Returns the fitted model.
    """
    clf = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    clf.fit(X)
    return clf

def score_iforest(clf, X):
    """
    Returns:
      - scores: anomaly scores (the higher, the more normal in scikit-learn; we invert for intuitive 'higher=worse')
      - is_outlier: boolean mask where True means anomaly
    """
    # decision_function: positive = inlier, negative = outlier
    decisions = clf.decision_function(X)  # higher means more normal
    # Convert to anomaly scores where higher is worse by inverting
    scores = -decisions
    preds = clf.predict(X)  # 1 for inlier, -1 for outlier
    is_outlier = preds == -1
    return scores, is_outlier
