"""Chronological split by forecast issue day.

A day is not shuffled, and it is not shared between train, validation and
test. Train issue days end before validation, and validation ends before test.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from forecasting.config import TRAIN_FRACTION, VAL_FRACTION


class LeakageError(ValueError):
    """A split or a feature used something that was not known at issue time."""


@dataclass
class IssueSplit:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame


def split_by_issue(
    frame: pd.DataFrame,
    train_fraction: float = TRAIN_FRACTION,
    val_fraction: float = VAL_FRACTION,
) -> IssueSplit:
    if train_fraction <= 0 or val_fraction <= 0 or train_fraction + val_fraction >= 1:
        raise ValueError("Train and validation fractions must leave a non-empty test share")
    issues = list(pd.Series(frame["issued_at"].unique()).sort_values())
    n_issues = len(issues)
    if n_issues < 3:
        raise ValueError(f"Need at least 3 issue days to split, found {n_issues}")
    # 90 * 0.70 is 62.99999999999999 in float, and int() would drop a day.
    n_train = max(1, int(n_issues * train_fraction + 1e-6))
    n_val = max(1, int(n_issues * val_fraction + 1e-6))
    if n_train + n_val >= n_issues:
        n_val = 1
        n_train = n_issues - 2
    train_issues = set(issues[:n_train])
    val_issues = set(issues[n_train : n_train + n_val])
    test_issues = set(issues[n_train + n_val :])
    split = IssueSplit(
        train=frame.loc[frame["issued_at"].isin(train_issues)].copy(),
        val=frame.loc[frame["issued_at"].isin(val_issues)].copy(),
        test=frame.loc[frame["issued_at"].isin(test_issues)].copy(),
    )
    assert_chronological(split)
    return split


def assert_chronological(split: IssueSplit) -> None:
    if split.train.empty or split.val.empty or split.test.empty:
        raise LeakageError("Train, validation and test must all contain rows")
    train_end = split.train["issued_at"].max()
    val_start = split.val["issued_at"].min()
    val_end = split.val["issued_at"].max()
    test_start = split.test["issued_at"].min()
    if not (train_end < val_start < test_start and val_end < test_start):
        raise LeakageError(
            "Issue days overlap or are out of order. "
            f"Train ends {train_end}, validation is {val_start} to {val_end}, "
            f"test starts {test_start}."
        )
    train_ids = set(split.train["issued_at"])
    val_ids = set(split.val["issued_at"])
    test_ids = set(split.test["issued_at"])
    if train_ids & val_ids or val_ids & test_ids or train_ids & test_ids:
        raise LeakageError("An issue day is in more than one part of the split")


def issue_bounds(frame: pd.DataFrame) -> dict:
    stamps = pd.Series(frame["issued_at"].unique()).sort_values()
    return {
        "n_issues": int(len(stamps)),
        "first": pd.Timestamp(stamps.iloc[0]).isoformat(),
        "last": pd.Timestamp(stamps.iloc[-1]).isoformat(),
    }
