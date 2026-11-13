"""Render every participant-facing PsychoPy screen to PNG + a PDF storyboard.

No device, no keyboard input, no data files: each screen is drawn with the
real stimulus objects from ``code/psychopy_fun.py`` / ``participant_controls.py``
and captured from the back buffer.

Usage (from pleasure_experiments/):
    ~/psychopy_env/bin/python storyboard.py                 # en + it, 1920x1080
    ~/psychopy_env/bin/python storyboard.py --lang it --size 2560 1440

Output: storyboard/storyboard_<lang>.pdf and storyboard/<lang>/<tree>/*.png
Set --size to the resolution of the lab monitor: the stimuli use pixel units,
so layout (wrapping, overlaps, off-screen text) depends on it.
"""

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from psychopy import visual  # noqa: E402

WINDOW_SIZE = (1920, 1080)


class _StoryboardWindow(visual.Window):
    """Same window as the experiment, but windowed at a fixed size."""

    def __init__(self, *args, **kwargs):
        kwargs.update(fullscr=False, size=WINDOW_SIZE, screen=0, allowGUI=False)
        super().__init__(*args, **kwargs)


visual.Window = _StoryboardWindow

from pleasure_experiments.code import psychopy_fun as pf  # noqa: E402
from pleasure_experiments.code.participant_controls import (  # noqa: E402
    get_participant_controls,
)

# Practice copy lives inside the practice functions; mirror the keys here.
PAIN_PRACTICE = ["pain_yes", "pain_no", "pain_quit", "orgasm"]
PAIN_FEEDBACK = ["correct", "wrong_pain_yes", "wrong_pain_no", "wrong_quit",
                 "wrong_orgasm", "complete"]
PLEASURE_PRACTICE = ["pleasure_yes", "vibration_no", "pain_down"]
PLEASURE_FEEDBACK = ["wrong_yes", "wrong_no", "wrong_pain_down"]


def _practice_copy(func, language):
    """Pull the `copy` dict literal out of a practice function's source."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(func).lstrip())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and getattr(node.targets[0], "id", None) == "copy"):
            return ast.literal_eval(node.value.value)[language]
    raise RuntimeError(f"No copy dict in {func.__name__}")


class Storyboard:
    def __init__(self, language, out_dir):
        self.language = language
        self.out_dir = out_dir / language
        if self.out_dir.exists():  # drop PNGs from earlier runs
            import shutil
            shutil.rmtree(self.out_dir)
        self.display = pf.psycho_stuff(language=language)
        (self.win, self.fixation, self.quality, self.quality_question,
         self.no_label, self.yes_label, self.ready_text, self.pain_label,
         self.intensity_question, self.intensity_scale,
         self.intensity_instruction) = self.display
        self.win.mouseVisible = False
        self.controls = get_participant_controls(self.win, "storyboard", language)
        self.pages = []  # (path tuple, source hint, PIL image)
        self.t = lambda key: pf.participant_text(key, language)

    # -- capture ----------------------------------------------------------
    def capture(self, path, source, *stims):
        for stim in stims:
            stim.draw()
        self.win.getMovieFrame(buffer="back")
        image = self.win.movieFrames.pop().convert("RGB")
        self.win.flip()
        self.pages.append((path, source, image))
        folder = self.out_dir.joinpath(*[_slug(p) for p in path[:-1]])
        folder.mkdir(parents=True, exist_ok=True)
        image.save(folder / f"{len(self.pages):02d}_{_slug(path[-1])}.png")

    # -- reusable screens ---------------------------------------------------
    def text_screen(self, path, source, message, pos=(0, 0), wrap=1800):
        stim = visual.TextStim(
            self.win, text=message, color=pf.TEXT_COLOR, colorSpace="rgb255",
            height=pf._scaled_font_size(pf.fontsize),
            wrapWidth=pf._scaled_font_size(wrap), font=pf.font_type, pos=pos)
        self.capture(path, source, stim, self.controls.banner)

    def ready(self, path, key, source):
        self.ready_text.text = self.t(key)
        self.capture(path, source, self.ready_text, self.controls.banner)

    def fixation_screen(self, path):
        self.capture(path, "stimulation_utils.py run_trial (fixation)",
                     self.fixation)

    def pause_screen(self, path, practice=False):
        self.capture(path, "participant_controls.py _pause_for_resume",
                     self.fixation, self.controls.pause_message)
        if not practice:  # practice: S resumes directly
            self.capture(path[:-1] + (path[-1] + " - after S",),
                         "participant_controls.py _ask_resume",
                         self.controls.resume_question)

    def binary_response(self, base, question_key):
        src = "stimulation_utils.py run_trial (binary response)"
        self.quality_question.text = self.t(question_key)
        self.no_label.text = f"←\n{self.t('no')}"
        self.yes_label.text = f"→\n{self.t('yes')}"
        self.quality.reset()
        options = [("LEFT/No", self.no_label), ("RIGHT/Yes", self.yes_label)]
        if question_key == "pleasure_question":  # DOWN = pain (1000)
            options.append(("DOWN/Painful", self.pain_label))
        labels = [label for _, label in options]
        for label in labels:
            label.color = "white"  # run_trial overrides TEXT_COLOR
        self.capture(base + ("Response - waiting",), src, self.quality,
                     *labels, self.quality_question, self.controls.banner)
        for name, label in options:
            label.color = "lightcoral"
            self.capture(base + (f"Response - {name} pressed",), src,
                         *labels, self.quality_question, self.controls.banner)
            label.color = "white"

    def vas(self, base, question, rating, confirmed=False, source=None,
            label=None):
        source = source or "stimulation_utils.py run_trial (intensity VAS)"
        self.intensity_question.text = question
        self.intensity_scale.reset()
        self.intensity_scale.setRating(rating)
        color = "lightcoral" if confirmed else pf.VAS_MARKER_COLOR
        self.intensity_scale.markerColor = color
        self.intensity_scale.markerFillColor = color
        stims = [self.intensity_question, self.intensity_scale]
        if not confirmed:
            stims.append(self.intensity_instruction)
        label = label or (f"VAS rating={rating}"
                          + (" confirmed (UP)" if confirmed else ""))
        self.capture(base + (label,), source, *stims, self.controls.banner)

    # -- experiment flow ----------------------------------------------------
    def build(self):
        lang = self.language
        prac = _practice_copy(pf.run_participant_practice, lang)
        vasc = _practice_copy(pf.run_vas_practice, lang)
        prac_src = "psychopy_fun.py run_participant_practice"
        vas_src = "psychopy_fun.py run_vas_practice"

        # 1. Annoyance threshold --------------------------------------------
        s = ("1 Annoyance threshold",)
        self.ready(s + ("Ready screen",), "annoyance_threshold_ready",
                   "thresholding.py run_threshold (ready)")
        self.quality_question.text = self.t("annoyance_question")
        self.no_label.color = self.yes_label.color = "white"
        k = s + ("Pain practice",)
        for key in PAIN_PRACTICE:
            self.prac_question(k + (f"Question: {key}",), prac[key], prac_src)
        for key in PAIN_FEEDBACK:
            self.text_screen(k + (f"Feedback: {key}",),
                             prac_src + " show", prac[key], pos=(0, 350))
        self.pause_screen(k + ("Orgasm pause (O)",), practice=True)
        t = s + ("Trial",)
        self.fixation_screen(t + ("Fixation / stimulation",))
        self.binary_response(t, "annoyance_question")

        # 2. Pleasure threshold ---------------------------------------------
        s = ("2 Pleasure threshold",)
        self.text_screen(s + ("Break (before stage)",),
                         "psychopy_fun.py show_break_review",
                         self.t("break"), wrap=1000)
        self.ready(s + ("Ready screen",), "pleasure_threshold_ready",
                   "thresholding.py run_threshold (ready)")
        k = s + ("Pleasure practice",)
        self.text_screen(k + ("Question has changed",), prac_src + " show",
                         prac["pleasure_intro"])
        self.quality_question.text = self.t("pleasure_question")
        for key in PLEASURE_PRACTICE:
            self.prac_question(k + (f"Question: {key}",), prac[key], prac_src,
                               pain=True)
        for key in PLEASURE_FEEDBACK:
            self.text_screen(k + (f"Feedback: {key}",),
                             prac_src + " show", prac[key], pos=(0, 350))
        t = s + ("Trial",)
        self.fixation_screen(t + ("Fixation / stimulation",))
        self.binary_response(t, "pleasure_question")

        # 3. Final experiment -----------------------------------------------
        s = ("3 Final experiment",)
        self.text_screen(s + ("Break / validation review",),
                         "psychopy_fun.py show_break_review",
                         self.t("break"), wrap=1000)
        v = s + ("VAS practice",)
        self.text_screen(v + ("Intro",), vas_src, vasc["intro"])
        for name, rating in (("strong", 0), ("strong", 50), ("faint", 0)):
            self.intensity_question.italic = True
            self.vas(v, vasc[name], rating, source=vas_src,
                     label=f"{name} vibration, rating={rating}")
            self.intensity_question.italic = False
        self.text_screen(v + ("Recorded value",), vas_src,
                         vasc["recorded"].format(rating=50))
        self.text_screen(v + ("Retry (strong <= faint)",), vas_src,
                         vasc["retry"])
        self.text_screen(v + ("Complete",), vas_src, vasc["complete"])
        t = s + ("Trial (habituation + main trials)",)
        self.fixation_screen(t + ("Fixation / stimulation",))
        self.binary_response(t, "pleasure_question")
        q = self.t("intensity_question")
        for rating in (0, 50, 100):
            self.vas(t, q, rating)
        self.vas(t, q, 50, confirmed=True)
        self.ready(s + ("Ready screen (before main trials)",), "final_ready",
                   "pleasure_pipeline.py run_final_pleasure_trials (ready)")
        self.pause_screen(s + ("Orgasm pause (O)",))
        self.capture(s + ("Quit confirmation (E)",),
                     "participant_controls.py _confirm_quit",
                     self.controls.quit_question)

    def prac_question(self, path, message, src, pain=False):
        text = visual.TextStim(
            self.win, text=message, color=pf.TEXT_COLOR, colorSpace="rgb255",
            height=pf._scaled_font_size(pf.fontsize),
            wrapWidth=pf._scaled_font_size(1800), font=pf.font_type,
            pos=(0, 350), italic=True)
        extra = [self.pain_label] if pain else []
        self.capture(path, src + " show_response_practice", text,
                     self.quality_question, self.no_label, self.yes_label,
                     *extra, self.controls.banner)


def _slug(text):
    keep = "".join(c if c.isalnum() or c in " -_=" else "_" for c in text)
    return "_".join(keep.split())


def _font(size):
    import matplotlib
    path = Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"
    return ImageFont.truetype(str(path), size)


def write_pdf(pages, pdf_path, language):
    width = pages[0][2].width
    header_h = 90
    font_title, font_src = _font(34), _font(24)

    rendered, toc = [], []
    seen = []
    for number, (path, source, image) in enumerate(pages, start=1):
        page = Image.new("RGB", (width, image.height + header_h), "white")
        page.paste(image, (0, header_h))
        draw = ImageDraw.Draw(page)
        draw.text((20, 10), f"[{number}]  " + "  ›  ".join(path),
                  fill="black", font=font_title)
        draw.text((20, 54), f"source: {source}   |   window "
                  f"{image.width}x{image.height}px", fill="#555", font=font_src)
        rendered.append(page)
        for depth, part in enumerate(path):
            if tuple(path[:depth + 1]) not in seen:
                seen.append(tuple(path[:depth + 1]))
                toc.append((depth, part, number))

    # Table-of-contents pages (tree view).
    line_h, top = 40, 110
    per_page = (rendered[0].height - top - 40) // line_h
    toc_pages = []
    for start in range(0, len(toc), per_page):
        page = Image.new("RGB", rendered[0].size, "white")
        draw = ImageDraw.Draw(page)
        draw.text((40, 30), f"Participant screens — language: {language}",
                  fill="black", font=_font(48))
        for i, (depth, part, num) in enumerate(toc[start:start + per_page]):
            y = top + i * line_h
            draw.text((60 + depth * 60, y), ("└ " if depth else "") + part,
                      fill="black", font=_font(28))
            draw.text((width - 200, y), f"[{num}]", fill="#555",
                      font=_font(28))
        toc_pages.append(page)
    offset = len(toc_pages)
    # Page numbers in the TOC refer to screen numbers; note the offset.
    draw = ImageDraw.Draw(toc_pages[0])
    draw.text((40, rendered[0].height - 40),
              f"(screen [n] is PDF page n+{offset})", fill="#555",
              font=_font(22))

    all_pages = toc_pages + rendered
    all_pages[0].save(pdf_path, save_all=True, append_images=all_pages[1:],
                      resolution=150)

    try:  # optional clickable bookmarks
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append(reader)
    parents = {}
    for depth, part, num in toc:
        parent = parents.get(depth - 1)
        parents[depth] = writer.add_outline_item(part, num - 1 + offset,
                                                 parent=parent)
    writer.write(pdf_path)


def main():
    global WINDOW_SIZE
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--lang", nargs="+", default=["en", "it"],
                        choices=["en", "it"])
    parser.add_argument("--size", nargs=2, type=int, default=list(WINDOW_SIZE),
                        metavar=("W", "H"))
    parser.add_argument("--out", type=Path, default=EXPERIMENT_DIR / "storyboard")
    args = parser.parse_args()
    WINDOW_SIZE = tuple(args.size)

    for language in args.lang:
        board = Storyboard(language, args.out)
        try:
            board.build()
        finally:
            board.win.close()
        pdf_path = args.out / f"storyboard_{language}.pdf"
        write_pdf(board.pages, pdf_path, language)
        print(f"{language}: {len(board.pages)} screens -> {pdf_path}")


if __name__ == "__main__":
    main()
