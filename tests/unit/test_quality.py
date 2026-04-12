"""Tests for quality check — degraded response detection."""
from __future__ import annotations

from solvela.quality import DegradedReason, check_degraded


class TestEmptyContent:
    def test_empty_content_is_degraded(self) -> None:
        assert check_degraded("") == DegradedReason.EMPTY_CONTENT

    def test_whitespace_only_is_degraded(self) -> None:
        assert check_degraded("   \n\t  ") == DegradedReason.EMPTY_CONTENT


class TestKnownErrorPhrases:
    def test_known_error_phrase(self) -> None:
        assert (
            check_degraded("I cannot help with that request.")
            == DegradedReason.KNOWN_ERROR_PHRASE
        )

    def test_case_insensitive_error_phrase(self) -> None:
        assert (
            check_degraded("As An AI language model, I think this is fine.")
            == DegradedReason.KNOWN_ERROR_PHRASE
        )

    def test_im_sorry_phrase(self) -> None:
        assert (
            check_degraded("I'm sorry, but I can't do that.")
            == DegradedReason.KNOWN_ERROR_PHRASE
        )


class TestRepetitiveLoop:
    def test_repetitive_loop(self) -> None:
        # A 3-word phrase repeated 20 times (60 words total, well above 15)
        content = " ".join(["the quick brown"] * 20)
        assert check_degraded(content) == DegradedReason.REPETITIVE_LOOP


class TestTruncatedMidWord:
    def test_truncated_mid_word(self) -> None:
        # >100 chars ending with alphanumeric
        content = "This is a long response that contains many words and goes on " + "a" * 50 + "b"
        assert len(content) > 100
        assert check_degraded(content) == DegradedReason.TRUNCATED_MID_WORD

    def test_content_ending_with_period_not_truncated(self) -> None:
        # >100 chars ending with period — not truncated
        content = "This is a perfectly normal response that happens to be quite long and contains enough words to exceed the threshold easily."
        assert len(content) > 100
        assert check_degraded(content) is None


class TestNormalContent:
    def test_normal_content_not_degraded(self) -> None:
        assert check_degraded("The capital of France is Paris.") is None
