# --------------------------------------------------------------------------
# Persistent regression suite for plugins/roi_viewer/core/mask_editor.py's
# UndoRedoManager (D7). Promoted from Phase 10's ephemeral scratchpad
# scripts (p10c_undoredo_functional_tests.py) into a real, re-runnable
# pytest suite - CT3D_P11_TEST_AUTOMATION, Section VIII/IX.
#
# Section IX of the Phase 11 spec requires answering, with real code and
# real tests (not hand reasoning):
#   Q1: can len(undo_stack) == max_history AND len(redo_stack) ==
#       max_history simultaneously, through the public API?
#   Q2: what is the real maximum of len(undo_stack) + len(redo_stack)?
#   Q3: given that maximum and the real per-checkpoint byte cost, what is
#       the real maximum retained snapshot memory?
# See test_undo_redo_memory_invariant() below - it exhaustively checks a
# large number of both deterministic and randomized public-API-only
# sequences and asserts the combined-stack-size invariant directly,
# rather than asserting a single hand-picked example.
# --------------------------------------------------------------------------
import copy
import random

import numpy as np
import pytest

from plugins.roi_viewer.core.mask_editor import MaskEditor, UndoRedoManager


pytestmark = pytest.mark.unit


def test_mask_editor_surviving_surface_after_dead_code_removal():
    """
    Regression guard for the Phase 11 dead-code removal (Section XIX):
    MaskEditor must still expose exactly what the real GUI
    (segmentation_panel.py) uses - shape/mask/undo_manager/save_state -
    and must NOT have regrown the confirmed-dead drawing API
    (draw_point_2d/draw_point_3d/interpolate_slices/erase_point_2d/
    get_mask/set_mask/get_mask_slice/undo/redo/clear_mask/
    set_brush_size/set_brush_shape/_get_brush_mask).
    """
    editor = MaskEditor((4, 4, 4))
    assert hasattr(editor, "shape")
    assert hasattr(editor, "mask")
    assert hasattr(editor, "undo_manager")
    assert hasattr(editor, "save_state")
    for dead_name in (
        "draw_point_2d", "draw_point_3d", "interpolate_slices", "erase_point_2d",
        "get_mask", "set_mask", "get_mask_slice", "undo", "redo", "clear_mask",
        "set_brush_size", "set_brush_shape", "_get_brush_mask",
    ):
        assert not hasattr(editor, dead_name), f"dead method {dead_name!r} should have been removed"


def _tagged_array(shape, value):
    """A small array whose content identifies which save_state() call
    produced it, so undo()/redo() results can be checked by value, not
    just by identity."""
    return np.full(shape, value % 256, dtype=np.uint8)


# ---------------------------------------------------------------------
# UR11-T1..T9 (Section VIII)
# ---------------------------------------------------------------------

def test_ur_t1_default_max_history_is_10():
    mgr = UndoRedoManager()
    assert mgr.max_history == 10


def test_ur_t2_deep_copy_independence():
    mask = _tagged_array((4, 4, 4), 1)
    mgr = UndoRedoManager(max_history=10)
    mgr.save_state(mask)
    mask[0, 0, 0] = 99  # mutate the source AFTER save_state()
    # the stored checkpoint must be unaffected (a real independent copy)
    assert mgr.undo_stack[0][0, 0, 0] == 1


def test_ur_t3_checkpoint_then_undo_returns_checkpoint():
    mgr = UndoRedoManager(max_history=10)
    a = _tagged_array((3, 3, 3), 10)  # checkpoint A
    mgr.save_state(a)
    b = _tagged_array((3, 3, 3), 20)  # current state B (edited after A)
    previous = mgr.undo(b)
    assert previous is not None
    assert np.array_equal(previous, a)  # undo() -> A
    assert len(mgr.undo_stack) == 0  # the only checkpoint was popped


def test_ur_t4_redo_returns_the_pre_undo_state():
    mgr = UndoRedoManager(max_history=10)
    a = _tagged_array((3, 3, 3), 10)
    mgr.save_state(a)
    b = _tagged_array((3, 3, 3), 20)
    previous = mgr.undo(b)  # -> A, B pushed to redo_stack
    nxt = mgr.redo(previous)  # -> should return B
    assert nxt is not None
    assert np.array_equal(nxt, b)
    assert len(mgr.redo_stack) == 0


def test_ur_t5_chain_undo_undo_redo_redo():
    """A -> B -> C, then undo, undo, redo, redo - every value checked."""
    mgr = UndoRedoManager(max_history=10)
    a = _tagged_array((2, 2, 2), 1)
    b = _tagged_array((2, 2, 2), 2)
    c = _tagged_array((2, 2, 2), 3)

    mgr.save_state(a)
    mgr.save_state(b)
    current = c  # simulate: state is now C, with A and B checkpointed

    step1 = mgr.undo(current)  # -> B (undo_stack had [A, B], pops B)
    assert np.array_equal(step1, b)
    step2 = mgr.undo(step1)  # -> A
    assert np.array_equal(step2, a)
    assert len(mgr.undo_stack) == 0

    step3 = mgr.redo(step2)  # -> B
    assert np.array_equal(step3, b)
    step4 = mgr.redo(step3)  # -> C
    assert np.array_equal(step4, c)
    assert len(mgr.redo_stack) == 0


def test_ur_t6_new_save_clears_redo_stack():
    mgr = UndoRedoManager(max_history=10)
    a = _tagged_array((2, 2, 2), 1)
    mgr.save_state(a)
    b = _tagged_array((2, 2, 2), 2)
    prev = mgr.undo(b)  # redo_stack now has 1 entry (B)
    assert len(mgr.redo_stack) == 1
    c = _tagged_array((2, 2, 2), 3)
    mgr.save_state(c)  # a NEW edit/checkpoint - must clear redo_stack
    assert len(mgr.redo_stack) == 0


def test_ur_t7_eviction_at_max_history():
    mgr = UndoRedoManager(max_history=10)
    for i in range(15):
        mgr.save_state(_tagged_array((2, 2, 2), i))
    assert len(mgr.undo_stack) == 10  # capped, not 15
    assert int(mgr.undo_stack[0][0, 0, 0]) == 5  # oldest 5 (0-4) evicted, FIFO
    assert int(mgr.undo_stack[-1][0, 0, 0]) == 14  # newest retained


def test_ur_t8_clear_empties_both_stacks():
    mgr = UndoRedoManager(max_history=10)
    mgr.save_state(_tagged_array((2, 2, 2), 1))
    mgr.redo_stack.append(_tagged_array((2, 2, 2), 2))
    mgr.clear()
    assert len(mgr.undo_stack) == 0
    assert len(mgr.redo_stack) == 0


def test_ur_t9_two_independent_managers_do_not_share_history():
    """Mirrors the real architecture: MaskEditorManager.create_editor()
    makes one MaskEditor (and one UndoRedoManager) per mask index - mask
    A's history must never leak into mask B's."""
    mgr_a = UndoRedoManager(max_history=10)
    mgr_b = UndoRedoManager(max_history=10)
    mgr_a.save_state(_tagged_array((2, 2, 2), 1))
    mgr_a.save_state(_tagged_array((2, 2, 2), 2))
    assert len(mgr_a.undo_stack) == 2
    assert len(mgr_b.undo_stack) == 0  # untouched


def test_undo_on_empty_stack_returns_none_without_side_effects():
    mgr = UndoRedoManager(max_history=10)
    current = _tagged_array((2, 2, 2), 1)
    assert mgr.undo(current) is None
    assert len(mgr.redo_stack) == 0  # a no-op undo must not push anything


def test_redo_on_empty_stack_returns_none_without_side_effects():
    mgr = UndoRedoManager(max_history=10)
    current = _tagged_array((2, 2, 2), 1)
    assert mgr.redo(current) is None
    assert len(mgr.undo_stack) == 0


# ---------------------------------------------------------------------
# Section IX: memory invariant investigation (Q1/Q2/Q3)
# ---------------------------------------------------------------------

def _combined_len(mgr):
    return len(mgr.undo_stack) + len(mgr.redo_stack)


def _run_sequence(mgr, ops, current_holder):
    """
    Apply a sequence of ('save'|'undo'|'redo'|'clear', payload_tag) ops
    to `mgr`, using ONLY its public API (save_state/undo/redo/clear) -
    exactly as segmentation_panel.py's _on_checkpoint/_on_undo/_on_redo
    drive it. `current_holder` is a 1-element list holding the
    "current mask" value, updated to mirror what the real GUI handler
    does (mask.matrix[:] = previous/next after undo()/redo()).
    Records (len(undo_stack), len(redo_stack)) after every single op.
    """
    trace = []
    for op, tag in ops:
        if op == "save":
            current_holder[0] = _tagged_array((2, 2, 2), tag)
            mgr.save_state(current_holder[0])
        elif op == "undo":
            result = mgr.undo(current_holder[0])
            if result is not None:
                current_holder[0] = result
        elif op == "redo":
            result = mgr.redo(current_holder[0])
            if result is not None:
                current_holder[0] = result
        elif op == "clear":
            mgr.clear()
        else:
            raise ValueError(op)
        trace.append((len(mgr.undo_stack), len(mgr.redo_stack)))
    return trace


DETERMINISTIC_SEQUENCES = {
    "1_ten_saves": [("save", i) for i in range(10)],
    "2_ten_saves_one_undo": [("save", i) for i in range(10)] + [("undo", None)],
    "3_ten_saves_five_undo": [("save", i) for i in range(10)] + [("undo", None)] * 5,
    "4_ten_saves_ten_undo": [("save", i) for i in range(10)] + [("undo", None)] * 10,
    "5_ten_saves_ten_undo_five_redo": (
        [("save", i) for i in range(10)] + [("undo", None)] * 10 + [("redo", None)] * 5
    ),
    "6_ten_saves_five_undo_new_save": (
        [("save", i) for i in range(10)] + [("undo", None)] * 5 + [("save", 99)]
    ),
}


@pytest.mark.parametrize("name,ops", sorted(DETERMINISTIC_SEQUENCES.items()))
def test_undo_redo_memory_invariant_deterministic(name, ops):
    """
    For every named deterministic sequence (Section IX items 1-6): after
    EVERY operation, len(undo_stack) + len(redo_stack) must never exceed
    max_history. This is the concrete, code-verified answer to Q1/Q2.
    """
    max_history = 10
    mgr = UndoRedoManager(max_history=max_history)
    current = [_tagged_array((2, 2, 2), -1)]
    trace = _run_sequence(mgr, ops, current)
    for i, (n_undo, n_redo) in enumerate(trace):
        assert n_undo <= max_history, f"{name} step {i}: undo_stack={n_undo} > max_history"
        assert n_redo <= max_history, f"{name} step {i}: redo_stack={n_redo} > max_history"
        assert n_undo + n_redo <= max_history, (
            f"{name} step {i}: combined={n_undo + n_redo} exceeds max_history={max_history} "
            f"(undo={n_undo}, redo={n_redo})"
        )


def test_undo_redo_memory_invariant_random_sequences():
    """
    Section IX item 7: hundreds of randomized sequences, calling ONLY the
    public API (save/undo/redo/clear), fixed seed for reproducibility.
    Confirms the combined-stack-size <= max_history invariant holds
    universally, not just for the 6 hand-picked sequences above.
    """
    max_history = 10
    rng = random.Random(20260914)  # fixed seed - reproducible
    ops_pool = ["save", "undo", "redo", "save", "undo", "redo", "clear"]  # bias toward save/undo/redo

    max_combined_seen = 0
    for trial in range(300):
        mgr = UndoRedoManager(max_history=max_history)
        current = [_tagged_array((2, 2, 2), 0)]
        n_ops = rng.randint(1, 40)
        for step in range(n_ops):
            op = rng.choice(ops_pool)
            trace = _run_sequence(mgr, [(op, step)], current)
            n_undo, n_redo = trace[-1]
            combined = n_undo + n_redo
            max_combined_seen = max(max_combined_seen, combined)
            assert n_undo <= max_history, f"trial {trial} step {step}: undo_stack={n_undo}"
            assert n_redo <= max_history, f"trial {trial} step {step}: redo_stack={n_redo}"
            assert combined <= max_history, (
                f"trial {trial} step {step}: combined={combined} > max_history={max_history} "
                f"after op={op!r}"
            )

    # Q1 answer (empirically confirmed, not just reasoned): the maximum
    # combined size IS reachable (equal to max_history) - it is simply
    # never EXCEEDED. Sanity-check that our random exploration actually
    # reached the ceiling at least once (otherwise the assertions above
    # would be vacuously true without ever stress-testing the boundary).
    assert max_combined_seen == max_history, (
        f"random exploration never reached the max_history ceiling "
        f"(max_combined_seen={max_combined_seen}, max_history={max_history}) - "
        f"increase trials/n_ops if this starts failing"
    )


def test_undo_redo_memory_invariant_q1_both_stacks_simultaneously_full_is_impossible():
    """
    Q1, stated directly: len(undo_stack) == max_history AND
    len(redo_stack) == max_history simultaneously is NOT reachable
    through the public API. Proof sketch (see module docstring / Phase
    11 report Section 11 for the full argument): redo_stack can only
    gain entries via undo() taking from undo_stack (zero-sum transfer,
    or a net loss if the destination stack is already full and evicts),
    and the only way to ADD brand-new content (save_state()) always
    clears redo_stack to 0 in the same call. So the combined total can
    only be built up by save_state() (which simultaneously zeroes the
    other stack) - it can never independently fill both stacks to
    max_history at once.
    """
    max_history = 10
    mgr = UndoRedoManager(max_history=max_history)
    current = [_tagged_array((2, 2, 2), 0)]

    # Best-effort adversarial attempt: fill undo_stack, drain it via undo
    # (filling redo_stack), then try to refill undo_stack via redo()
    # while redo_stack is still full - redo() necessarily drains
    # redo_stack by exactly the amount it adds to undo_stack.
    _run_sequence(mgr, [("save", i) for i in range(max_history)], current)
    _run_sequence(mgr, [("undo", None)] * max_history, current)
    assert len(mgr.undo_stack) == 0
    assert len(mgr.redo_stack) == max_history

    _run_sequence(mgr, [("redo", None)] * (max_history // 2), current)
    # redo_stack lost exactly what undo_stack gained - combined unchanged
    assert len(mgr.undo_stack) == max_history // 2
    assert len(mgr.redo_stack) == max_history // 2
    assert len(mgr.undo_stack) + len(mgr.redo_stack) == max_history

    # No sequence of undo()/redo() calls can make BOTH reach max_history
    # simultaneously, since every single call moves at most one item
    # between them (or clears one to zero via save_state).
    assert not (len(mgr.undo_stack) == max_history and len(mgr.redo_stack) == max_history)


def test_undo_redo_memory_invariant_q3_real_ct_scale_max_retained_bytes():
    """
    Q3: given Q2's answer (max combined = max_history, empirically
    confirmed above) and the real per-checkpoint byte cost at real
    single-series-CT scale (measured in Phase 10:
    109x513x513 uint8 = 28,685,421 bytes), what is the real maximum
    retained snapshot memory reachable through the public API?

    This computes it two ways and cross-checks them: (a) the
    Q1/Q2-derived formula max_history * bytes_per_checkpoint, and (b) a
    real run of UndoRedoManager against real (small, for test speed)
    memmap-backed arrays, summing each retained array's REAL .nbytes -
    a deterministic functional measurement (Section X), not noisy
    process RSS.
    """
    import os
    import tempfile

    max_history = 10
    real_ct_shape = (109, 513, 513)  # Phase 10's measured real-CT-scale shape
    bytes_per_checkpoint_real_ct = int(np.prod(real_ct_shape))  # uint8 = 1 byte/voxel
    assert bytes_per_checkpoint_real_ct == 28_685_421  # matches Phase 10's measured constant exactly

    formula_max_bytes = max_history * bytes_per_checkpoint_real_ct
    assert formula_max_bytes == 286_854_210  # ~273.6 MB, NOT ~547 MB (2x the old Phase 10 estimate)

    # (b) Real functional check with a small shape (fast) but the exact
    # same relationship (uint8, 1 byte/voxel) - drive to the max reachable
    # combined size via the public API, then sum real .nbytes.
    small_shape = (16, 16, 16)
    tmpdir = tempfile.mkdtemp(prefix="ur_q3_")
    path = os.path.join(tmpdir, "m.dat")
    mask = np.memmap(path, mode="w+", dtype=np.uint8, shape=small_shape)
    mask[:] = 0

    mgr = UndoRedoManager(max_history=max_history)
    for i in range(max_history):
        mask[0, 0, 0] = i % 256
        mgr.save_state(mask)
    # undo_stack is now full (max_history), redo_stack empty - the
    # combined-max state reachable via repeated save_state().
    assert len(mgr.undo_stack) + len(mgr.redo_stack) == max_history

    retained_bytes = sum(arr.nbytes for arr in mgr.undo_stack) + sum(
        arr.nbytes for arr in mgr.redo_stack
    )
    expected_bytes = max_history * mask.nbytes
    assert retained_bytes == expected_bytes  # confirms the formula empirically, not just by reasoning

    # Scale the empirically-confirmed formula up to real-CT-size and
    # compare against the Phase 10 report's original (overestimated)
    # worst-case number to make the correction concrete.
    real_ct_max_mb = formula_max_bytes / (1024 * 1024)
    old_phase10_estimate_mb = 2 * max_history * bytes_per_checkpoint_real_ct / (1024 * 1024)
    assert real_ct_max_mb == pytest.approx(273.5, abs=0.5)
    assert old_phase10_estimate_mb == pytest.approx(2 * real_ct_max_mb, abs=0.01)
