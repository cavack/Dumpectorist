from app.strategy.review import CandidateReview, classify_candidate


def test_candidate_starts_in_watch_when_structure_is_missing():
    review = CandidateReview(symbol="TEST")

    assert classify_candidate(review) == "WATCH"


def test_candidate_moves_to_review_after_structure_check():
    review = CandidateReview(symbol="TEST", structure_ok=True)

    assert classify_candidate(review) == "REVIEW"


def test_candidate_moves_to_ready_after_all_checks():
    review = CandidateReview(
        symbol="TEST",
        structure_ok=True,
        validation_ok=True,
        freshness_ok=True,
    )

    assert classify_candidate(review) == "READY"
