"""The participant-screen objects, bundled (no PsychoPy import, so it can be
used by modules that tests load without PsychoPy)."""

from collections import namedtuple

# Everything drawn on the participant screen, created once by
# psychopy_fun.psycho_stuff(). A plain tuple of the same 11 objects (e.g. in
# tests) also works: as_display() converts it.
Display = namedtuple("Display", [
    "win", "fixation", "quality", "quality_question", "no_label", "yes_label",
    "ready_text", "pain_label", "intensity_question", "intensity_scale",
    "intensity_instruction",
])


def as_display(display):
    return display if isinstance(display, Display) else Display(*display)
