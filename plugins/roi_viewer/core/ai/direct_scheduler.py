# --------------------------------------------------------------------------
# Direct interaction: when to run the model after a click (pure logic, no
# wx / VTK / model). feature/interactive-ai-direct-click.
#
# One click = one interaction, two stages:
#   "slice"   quick provisional feedback on the clicked slice (never Accept-able)
#   "volume"  the 3D candidate (smart initial box + all prompts)
# Latest wins, bounded: at most ONE job runs (the AI job controller allows
# no more) and at most ONE "pending" flag records that the prompt set
# changed meanwhile. When the running stage ends with that flag set, its
# result is NOT shown (it belongs to an older prompt set) and the slice
# stage starts again from the CURRENT prompts. No queue of prompt sets.
# Hover never triggers anything - only request() (a click / a box) does.
# --------------------------------------------------------------------------

STAGE_SLICE = "slice"
STAGE_VOLUME = "volume"

START_SLICE = "start_slice"
START_VOLUME = "start_volume"
DEFERRED = "deferred"
SHOW = "show"  # show this result, nothing else to run
SHOW_THEN_VOLUME = "show_then_volume"
DISCARD_THEN_SLICE = "discard_then_slice"
IDLE = "idle"


class DirectPreviewScheduler:
    def __init__(self, two_stage: bool = True):
        self.two_stage = bool(two_stage)
        self.stage = None  # running stage, or None
        self.pending = False
        self.started = {STAGE_SLICE: 0, STAGE_VOLUME: 0}
        self.discarded = 0

    @property
    def busy(self) -> bool:
        return self.stage is not None

    def _start(self, stage):
        self.stage = stage
        self.started[stage] += 1
        return START_SLICE if stage == STAGE_SLICE else START_VOLUME

    def first_stage(self):
        return STAGE_SLICE if self.two_stage else STAGE_VOLUME

    def request(self) -> str:
        """The prompt set changed (click / box / undo...)."""
        if self.stage is None:
            return self._start(self.first_stage())
        self.pending = True
        return DEFERRED

    def finished(self, stage, ok: bool = True) -> str:
        """The running stage ended (result or failure). Returns what to do
        with its result and what to run next."""
        if stage != self.stage:
            return IDLE  # not ours (e.g. after reset)
        self.stage = None
        if self.pending:
            self.pending = False
            self.discarded += 1
            self._start(self.first_stage())
            return DISCARD_THEN_SLICE
        if ok and stage == STAGE_SLICE:
            self._start(STAGE_VOLUME)
            return SHOW_THEN_VOLUME
        return SHOW if ok else IDLE

    def reset(self):
        """Cancel / clear prompts / project close: forget everything."""
        self.stage = None
        self.pending = False
