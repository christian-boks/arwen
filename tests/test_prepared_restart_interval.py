"""--restart-interval-seconds on the prepared single-domain door. CPU only.

A run resumed from a checkpoint may write its own checkpoints at another cadence, or none:
the restart identity tolerates the cadence (RESTART_TOLERATED_*_FIELDS), so an analysis
cycle's forecast can resume from an analysis checkpoint without writing ~40 GiB of
checkpoints nobody resumes from.  Box check (2026-10-15): a 50-minute resume with cadence 0
wrote no checkpoint and its rain was byte-identical to the 600 s resume's.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import pytest

from gpuwm import prepared_single_domain_forecast as door
from gpuwm.config import RunConfig
from gpuwm.core.model import RESTART_TOLERATED_EXPERIMENT_FIELDS, RESTART_TOLERATED_RUN_FIELDS


def _run(**changes):
    values = dict(nx=6, ny=4, nz=5, dx=3000.0, dy=3000.0, ztop=20000.0, dt=20.0, run_seconds=3600.0, restart_interval_s=600.0)
    values.update(changes)
    return RunConfig(**values)


@dataclass(frozen=True)
class _Domain:
    run: RunConfig


@dataclass(frozen=True)
class _Exp:
    """The two fields the override touches, shaped like ExperimentConfig."""

    restart_interval_s: float
    domains: tuple

    @property
    def root(self):
        return self.domains[0]


def _exp(seconds=600.0):
    return _Exp(restart_interval_s=seconds, domains=(_Domain(run=_run(restart_interval_s=seconds)),))


def test_the_restart_identity_tolerates_the_cadence():
    # The override is only sound while a checkpoint's identity leaves the cadence out.
    assert "restart_interval_s" in RESTART_TOLERATED_EXPERIMENT_FIELDS
    assert "restart_interval_s" in RESTART_TOLERATED_RUN_FIELDS


def test_no_override_and_an_equal_one_keep_the_experiment():
    exp = _exp()
    assert door._apply_restart_interval(exp, None) is exp
    assert door._apply_restart_interval(exp, 600.0) is exp


@pytest.mark.parametrize("seconds", [0.0, 1800.0])
def test_override_replaces_both_copies(seconds):
    out = door._apply_restart_interval(_exp(), seconds)
    assert out.restart_interval_s == seconds
    assert out.root.run.restart_interval_s == seconds
    assert out.root.run.run_seconds == 3600.0


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_override_refuses_a_bad_cadence(bad):
    with pytest.raises(ValueError, match="restart-interval-seconds"):
        door._apply_restart_interval(_exp(), bad)


def test_the_flag_parses_zero_and_refuses_negative():
    assert door._non_negative_finite_seconds("0") == 0.0
    assert door._non_negative_finite_seconds("600") == 600.0
    for bad in ("-5", "nan", "inf", "ten"):
        with pytest.raises(argparse.ArgumentTypeError):
            door._non_negative_finite_seconds(bad)
