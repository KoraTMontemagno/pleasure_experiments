from datetime import datetime

from .pleasure_outputs import append_csv as _append_csv
from .pleasure_outputs import now_iso as _now
from .pleasure_outputs import participant_output_dir

# Top-left corner (norm units) shared by the control banner and pause message.
_CORNER = (-0.97, 0.97)
_CORNER_TEXT_HEIGHT = 0.07


ORGASM_FIELDS = [
    "subject", "phase", "trial", "orgasm_start", "orgasm_end",
    "duration_s", "decision_time", "outcome",
]


class ParticipantControls:
    def __init__(self, win, subject, language):
        from psychopy import event, visual

        if language not in {"en", "it"}:
            raise ValueError("language must be 'en' or 'it'.")
        self.win = win
        self.subject = subject
        self.language = language
        self.event = event
        self.orgasm_reports_pending = 0
        self.phase = ""
        self.trial = ""
        output_dir = participant_output_dir(subject, "experiment")
        # every participant key event (O, S, E, resume/quit decisions)
        self.output_path = output_dir / f"sub-{subject}_participant_events.csv"
        # one row per orgasm: O (start) -> S (end) -> resume / end decision
        self.orgasm_path = output_dir / f"sub-{subject}_orgasm_events.csv"
        self._orgasm = None
        from .psychopy_fun import (
            TEXT_COLOR,
            font_type,
            fontsize,
            participant_text,
        )

        instructions = participant_text("control_banner", language)
        font_scale = fontsize / 80
        self.banner = visual.TextStim(
            win,
            text=instructions,
            color=TEXT_COLOR,
            colorSpace="rgb255",
            height=_CORNER_TEXT_HEIGHT * font_scale,
            pos=_CORNER,
            units="norm",
            wrapWidth=0.8,
            alignText="left",
            anchorHoriz="left",
            anchorVert="top",
            font=font_type,
        )
        self.fixation = visual.TextStim(
            win,
            text="+",
            color=TEXT_COLOR,
            colorSpace="rgb255",
            height=0.08 * font_scale,
            pos=(0, 0),
            units="norm",
            font=font_type,
        )
        self.pause_message = visual.TextStim(
            win,
            text=participant_text("pause_message", language),
            color=TEXT_COLOR,
            colorSpace="rgb255",
            height=_CORNER_TEXT_HEIGHT * font_scale,
            pos=_CORNER,
            units="norm",
            wrapWidth=1.5,
            alignText="left",
            anchorHoriz="left",
            anchorVert="top",
            font=font_type,
        )
        self.quit_question = visual.TextStim(
            win,
            text=participant_text("quit_confirm", language),
            color=TEXT_COLOR,
            colorSpace="rgb255",
            height=fontsize * font_scale,
            pos=(0, 0),
            units="pix",
            wrapWidth=1800 * font_scale,
            alignText="center",
            font=font_type,
        )
        self.resume_question = visual.TextStim(
            win,
            text=participant_text("resume_question", language),
            color=TEXT_COLOR,
            colorSpace="rgb255",
            # Same size as the other main screens (psychopy_fun._scaled_font_size).
            height=fontsize * font_scale,
            pos=(0, 0),
            units="pix",
            wrapWidth=1800 * font_scale,
            alignText="center",
            font=font_type,
        )

    def set_context(self, phase="", trial=""):
        self.phase = phase
        self.trial = trial

    def draw(self):
        self.banner.draw()

    def _record(self, event_name):
        _append_csv(
            self.output_path,
            ["timestamp", "subject", "event", "phase", "trial"],
            {"timestamp": _now(), "subject": self.subject, "event": event_name,
             "phase": self.phase, "trial": self.trial},
        )

    def _orgasm_started(self):
        self._orgasm = {"subject": self.subject, "phase": self.phase,
                        "trial": self.trial, "orgasm_start": _now(),
                        "_start": datetime.now()}

    def _orgasm_ended(self):
        if self._orgasm is not None:
            self._orgasm["orgasm_end"] = _now()
            self._orgasm["duration_s"] = round(
                (datetime.now() - self._orgasm["_start"]).total_seconds(), 3)

    def _orgasm_finished(self, outcome):
        """Write the orgasm row once the participant resumes or ends."""
        if self._orgasm is None:
            return
        row = {k: v for k, v in self._orgasm.items() if not k.startswith("_")}
        row.update(decision_time=_now(), outcome=outcome)
        _append_csv(self.orgasm_path, ORGASM_FIELDS, row)
        self._orgasm = None

    def _quit(self):
        self._orgasm_finished("ended experiment")
        self._record("participant_quit")
        raise KeyboardInterrupt("Participant chose to quit with E.")

    def _confirm_quit(self):
        """E pressed: ask "Are you sure?" (RIGHT = quit, LEFT = continue).

        Returns only if the participant cancels; otherwise ends the session.
        Escape (experimenter) still quits immediately.
        """
        self._record("quit_requested")
        while True:
            self.quit_question.draw()
            self.win.flip()
            keys = self.event.waitKeys(keyList=["left", "right", "escape"])
            normalized = {str(key).lower() for key in keys or []}
            if normalized.intersection({"right", "escape"}):
                self._quit()
            if "left" in normalized:
                self._record("quit_cancelled")
                return

    def _restore(self, fixation):
        """Back to the neutral fixation screen after an overlay screen.

        Screens that wait for a response redraw themselves every frame, so
        this only remains visible where the fixation cross belongs.
        """
        (fixation or self.fixation).draw()
        self.win.flip()

    def _pause_for_resume(self, fixation, ask_resume=True):
        if fixation is None:
            fixation = self.fixation
        while True:
            fixation.draw()
            # The pause message takes the banner's place in the top-left corner.
            self.pause_message.draw()
            self.win.flip()
            # Practice (ask_resume=False): E cannot end the session here.
            keys = ["s", "e", "escape"] if ask_resume else ["s", "escape"]
            pause_keys = self.event.waitKeys(keyList=keys)
            normalized = {str(key).lower() for key in pause_keys or []}
            if "escape" in normalized:
                self._quit()
            if "e" in normalized:
                self._confirm_quit()
                continue  # cancelled: back to the pause screen
            break
        if not ask_resume:
            return
        self._record("orgasm_ended")
        self._orgasm_ended()
        self._ask_resume()

    def _ask_resume(self):
        """After S: ask whether to resume (RIGHT/Yes) or end (LEFT/No)."""
        while True:
            self.resume_question.draw()
            self.win.flip()
            keys = self.event.waitKeys(
                keyList=["left", "right", "e", "escape"]
            )
            normalized = {str(key).lower() for key in keys or []}
            if "right" in normalized:
                self._record("participant_resumed")
                self._orgasm_finished("resumed")
                return
            if normalized.intersection({"left", "escape"}):
                self._quit()
            if "e" in normalized:
                self._confirm_quit()  # cancelled: ask again

    def practice_orgasm_pause(self, fixation=None):
        # Practice: S resumes directly, without the resume question.
        self._pause_for_resume(fixation, ask_resume=False)

    def process_keys(self, keys, fixation=None):
        normalized = {str(key).lower() for key in keys}
        if "escape" in normalized:
            self._quit()
        if "e" in normalized:
            self._confirm_quit()
            if "o" not in normalized:
                self._restore(fixation)
        if "o" not in normalized:
            return

        self._record("orgasm_reported")
        self._orgasm_started()
        self.orgasm_reports_pending += 1
        self._pause_for_resume(fixation)
        self._restore(fixation)

    def consume_orgasm_reports(self):
        reports = self.orgasm_reports_pending
        self.orgasm_reports_pending = 0
        return reports


def get_participant_controls(win, subject, language):
    controls = getattr(win, "_pleasure_participant_controls", None)
    if controls is None:
        controls = ParticipantControls(win, subject, language)
        win._pleasure_participant_controls = controls
    elif subject is not None and controls.subject != subject:
        raise ValueError("A PsychoPy window cannot be reused for another participant.")
    return controls
