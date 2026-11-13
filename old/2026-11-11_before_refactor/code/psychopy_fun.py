import math

from psychopy import core, event, monitors, visual

fontsize = 60
font_type = "DejaVu Sans"
arrow_font_type = "DejaVu Sans"
_BACKGROUND_COLOR = (90, 31, 35)
TEXT_COLOR = (226, 216, 206)
VAS_MARKER_COLOR = "darkred"  # intensity VAS marker before confirming
RESPONSE_LABEL_X = 450  # horizontal distance of the ← No / Yes → labels


def _scaled_font_size(reference_size):
    return reference_size * fontsize / 60


# Create a monitor (optional, avoids warnings)
#mon = monitors.Monitor("testMonitor", width=30, distance=60)  # Width in cm, Distance in cm

_PARTICIPANT_TEXT = {
    "en": {
        "pleasure_question": "Did you feel a pleasurable sensation?",
        "annoyance_question": "Did this vibration feel annoying or painful?",
        "no": "No",
        "yes": "Yes",
        "pain_option": "Painful / annoying",
        "intensity_question": "How intense was the vibration (not pleasure)?",
        "not_at_all": "Not at all",
        "extremely": "Extremely",
        "vas_instruction": "Use LEFT/RIGHT to move the marker and UP to confirm.",
        "pleasure_ready": (
            "In this part of the experiment, you will receive vibrations.\n\n"
            "After each vibration, use LEFT or RIGHT to indicate whether the "
            "sensation was pleasurable (← No, Yes →). Pleasure varies from "
            "person to person: if you only feel a vibration, answer No; if "
            "you feel pleasure similar to sexual stimulation, answer Yes. "
            "Always answer, even if you are unsure.\n\n"
            "If you feel pain or discomfort and want to stop, press E. If "
            "you have an orgasm, press O to pause; press S to resume or E "
            "to stop.\n\n"
            "Rate VIBRATION INTENSITY (not pleasure) with LEFT/RIGHT and "
            "confirm with UP.\n\nPress SPACE or ENTER when ready."
        ),
        "annoyance_threshold_ready": (
            "In this part of the experiment, you will receive vibrations.\n\n"
            "We want to identify intensities that feel annoying or painful "
            "so they can be avoided later. After each vibration, press LEFT "
            "if it was not annoying or painful (No), or RIGHT if it was "
            "annoying or painful (Yes). Answer based on how you experienced "
            "the vibration, even if you are unsure.\n\n"
            "If you want to stop the experiment, press E. If stimulation "
            "causes an orgasm, press O to pause; then press S to continue "
            "or E to stop.\n\nPress SPACE or ENTER when ready."
        ),
        "pleasure_threshold_ready": (
            "After each vibration, use LEFT for not pleasurable or RIGHT "
            "for pleasurable. If the vibration was painful or annoying but "
            "you want to continue, press DOWN (↓).\n\n"
            "If you feel pain or discomfort and want to "
            "stop, press E. If you have an orgasm, press O to pause; press "
            "S to resume or E to stop.\n\nPress SPACE or ENTER when ready."
        ),
        "final_ready": (
            "After each vibration, use LEFT or RIGHT to indicate whether "
            "the sensation was pleasurable (← No, Yes →). If it was painful "
            "or annoying but you want to continue, press DOWN (↓). If you "
            "feel pain or discomfort and want to stop, press E. If you have an "
            "orgasm, press O to pause; press S to resume or E to stop.\n\n"
            "Rate VIBRATION INTENSITY (not pleasure) with LEFT/RIGHT and "
            "confirm with UP.\n\nPress SPACE or ENTER when ready."
        ),
        "control_banner": "Press O to report an orgasm\nPress E to stop",
        "pause_message": "Orgasm recorded.\nTake your time, then press S to continue.",
        "resume_question": (
            "Orgasm ended.\n"
            "Do you want to resume the experiment or end it?\n\n"
            "← No, end          Yes, resume →"
        ),
        "quit_confirm": (
            "Are you sure you want to quit?\n"
            "This will end the experiment.\n\n"
            "← No, continue          Yes, quit →"
        ),
        "break": "You can take a break if you want.\nPress ENTER when you are ready to continue.",
    },
    "it": {
        "pleasure_question": "Hai provato una sensazione piacevole?",
        "annoyance_question": "Questa vibrazione è stata fastidiosa o dolorosa?",
        "no": "No",
        "yes": "Sì",
        "pain_option": "Doloroso / fastidioso \n (continua l'esperimento)",
        "intensity_question": "Quanto è stata intensa la vibrazione (non il piacere)?",
        "not_at_all": "Per niente",
        "extremely": "Estremamente",
        "vas_instruction": (
            "Usa le frecce SINISTRA/DESTRA per muovere il cursore "
            "e SU per confermare."
        ),
        "pleasure_ready": (
            "In questa parte dell'esperimento riceverai vibrazioni sul "
            "clitoride.\n\n Dopo ogni vibrazione, usa la tastiera e premi la freccetta SINISTRA o DESTRA per "
            "indicare se la sensazione è stata piacevole (← No, Sì →).\n\n"
            "Il piacere varia da persona a persona: se senti solo una "
            "vibrazione, indica no; se provi una sensazione di piacere "
            "simile a quella della stimolazione sessuale, indica sì. "
            "Fornisci sempre una risposta, anche se non sei sicura/o.\n\n"
            "Se vuoi interrompere l'esperimento, premi E. Nel caso la "
            "stimolazione causasse un orgasmo, premi O per mettere in pausa.\n\n"
            "Valuta l'intensità DELLA VIBRAZIONE (non del piacere) con "
            "SINISTRA/DESTRA e conferma con SU.\n\nPremi INVIO quando sei pront*."
        ),
        "annoyance_threshold_ready": (
            "In questa parte dell'esperimento riceverai vibrazioni sulla "
            "clitoride.\n\n"
            "Vogliamo capire quali intensità risultano fastidiose o "
            "dolorose, così da poterle evitare nella parte successiva.\n "
            "Dopo ogni vibrazione, usa la tastiera e premi la freccetta SINISTRA se non è stata fastidiosa "
            "o dolorosa (← No) e DESTRA se è stata fastidiosa o dolorosa "
            "(Sì →).\n Rispondi in base a come hai percepito la vibrazione, "
            "anche se non sei sicur*.\n\n"
            "Se vuoi interrompere l'esperimento, premi E. \nNel caso la "
            "stimolazione causasse un orgasmo, premi O."
            "\n\nPremi INVIO quando sei pront*.\n Inizieremo con una prova dei comandi per controllare che le istruzioni siano chiare"
        ),
        "pleasure_threshold_ready": (
            "In questa parte dell'esperimento testeremo la tua percezione del piacere \n"
            "Anche qui, riceverai delle vibrazioni sulla clitoride - questa volta però dovrai indicare se la sensazione è stata PIACEVOLE.\n\n "
            "Dopo ogni vibrazione, usa SINISTRA se la sensazione non è stata "
            "piacevole o DESTRA se è stata piacevole. \nSe la vibrazione è "
            "stata dolorosa o fastidiosa ma vuoi continuare, premi GIÙ (↓). "
            "\nCome prima, se provi dolore o "
            "fastidio e vuoi INTERROMPERE, premi E. \nSe hai un orgasmo, premi "
            "O per mettere in pausa..\n\n"
            "\n\nPremi INVIO quando sei pront*.\n Come prima, faremo delle prove sui comandi"
        ),
        "final_ready": (
            "Dopo ogni vibrazione, usa SINISTRA o DESTRA per indicare se la "
            "sensazione è stata piacevole (← No, Sì →). Se è stata dolorosa "
            "o fastidiosa ma vuoi continuare, premi GIÙ (↓). Se provi dolore o "
            "fastidio e vuoi interrompere, premi E. Se hai un orgasmo, premi "
            "O per mettere in pausa; poi premi S per riprendere o E per "
            "terminare.\n\n"
            "Valuta l'intensità DELLA VIBRAZIONE (non del piacere) con "
            "SINISTRA/DESTRA e conferma con SU.\n\nPremi INVIO quando sei pronta/o."
        ),
        "control_banner": "Premi O per segnalare un orgasmo\nPremi E per interrompere",
        "pause_message": "Orgasmo registrato.\nQuando vuoi, premi S per continuare.",
        "resume_question": (
            "Orgasmo terminato.\n"
            "Vuoi riprendere l'esperimento o terminarlo?\n\n"
            "← No, termina          Sì, riprendi →"
        ),
        "quit_confirm": (
            "Vuoi davvero uscire?\n"
            "L'esperimento verrà terminato.\n\n"
            "← No, continua          Sì, esci →"
        ),
        "break": "Puoi fare una pausa se vuoi.\nPremi INVIO quando vuoi continuare.",
    },
}


def participant_text(key, language="en"):
    if language not in _PARTICIPANT_TEXT:
        raise ValueError("language must be 'en' or 'it'.")
    try:
        return _PARTICIPANT_TEXT[language][key]
    except KeyError as exc:
        raise ValueError(f"Unknown participant text key: {key}") from exc


def psycho_stuff(
    question_text=None,
    instruction_text=None,
    language="en",
):
    if language not in {"en", "it"}:
        raise ValueError("language must be 'en' or 'it'.")

    translations = {
        key: participant_text(key, language)
        for key in (
            "pleasure_question",
            "no",
            "yes",
            "intensity_question",
            "not_at_all",
            "extremely",
            "vas_instruction",
            "pleasure_ready",
        )
    }
    if question_text is None:
        question_text = translations["pleasure_question"]
    if instruction_text is None:
        instruction_text = translations["pleasure_ready"]

    # Full screen?
    Full_screen = True
    
    # Create a PsychoPy window
    win = visual.Window(
    #    size= (500, 500),
        color=_BACKGROUND_COLOR,
        colorSpace="rgb255",
        units="pix",
        monitor="testMonitor",  # Avoids monitor warnings
        screen = 1,
        fullscr=Full_screen  # Set True if you want fullscreen
    )
    # fixation cross:
    fixation = visual.TextStim(
        win,
        text='+',
        color=TEXT_COLOR,
        colorSpace="rgb255",
        height=_scaled_font_size(80),
        pos=(0, 0)
    )
    
    quality_question = visual.TextStim(
        win,
        text=question_text,
        color=TEXT_COLOR,
        colorSpace="rgb255",
        height=_scaled_font_size(fontsize),
        pos=(0, +200),
        wrapWidth=_scaled_font_size(1800),
        font=font_type
    )

    no_label = visual.TextStim(
    win, text=f"←\n{translations['no']}", pos=(-RESPONSE_LABEL_X, -100), color=TEXT_COLOR, colorSpace="rgb255", height=_scaled_font_size(fontsize), font=arrow_font_type,
    )
    yes_label = visual.TextStim(
    win, text=f"→\n{translations['yes']}", pos=(RESPONSE_LABEL_X, -100), color=TEXT_COLOR, colorSpace="rgb255", height=_scaled_font_size(fontsize), font=arrow_font_type,
    )
    # DOWN = painful/annoying (response 1000); pleasure responses only.
    pain_label = visual.TextStim(
        win,
        text=f"↓\n{participant_text('pain_option', language)}",
        pos=(0, -300),
        wrapWidth=_scaled_font_size(1800),
        color=TEXT_COLOR,
        colorSpace="rgb255",
        height=_scaled_font_size(fontsize),
        font=font_type,
    )
    quality = visual.Slider(
    win=win,
        ticks=(1,2),
        size=(1.0, 0.1),
        pos=(0, -0.5),
        units='norm',
        labels=["",""],
        granularity=1,
        style='rating',
        labelColor=TEXT_COLOR,
        labelHeight=0.4,
        markerColor='blue',
        font=font_type,
        colorSpace="rgb255",
        lineColor=_BACKGROUND_COLOR,
    )
    # Hide the line by making its color match background
    #quality.marker.size = (0.01*2, 0.03*2)
    intensity_question = visual.TextStim(
        win,
        text=translations["intensity_question"],
        color=TEXT_COLOR,
        colorSpace="rgb255",
        height=_scaled_font_size(fontsize),
        pos=(0, 250),
        wrapWidth=_scaled_font_size(1800),
        font=font_type,
    )
    intensity_scale = visual.Slider(
        win=win,
        size=(1200, 60),
        pos=(0, -150),
        units="pix",
        labels=[translations["not_at_all"], translations["extremely"]],
        ticks=(0, 100),
        granularity=1,
        style="rating",
        color=TEXT_COLOR,
        colorSpace="rgb255",
        lineColor=TEXT_COLOR,
        labelHeight=_scaled_font_size(fontsize),
        markerColor=VAS_MARKER_COLOR,
        font=font_type,
    )
    intensity_scale.marker.size = (18, 30)
    intensity_instruction = visual.TextStim(
        win,
        text=translations["vas_instruction"],
        color=TEXT_COLOR,
        colorSpace="rgb255",
        height=_scaled_font_size(fontsize-20),
        pos=(0, -400),
        wrapWidth=_scaled_font_size(1800),
        font=font_type,
    )

    ready_text = visual.TextStim(
        win,
        text=instruction_text,
        color=TEXT_COLOR,
        colorSpace="rgb255",
        height=_scaled_font_size(fontsize),
        wrapWidth=_scaled_font_size(1800),
        font=font_type
    )

    return (
        win,
        fixation,
        quality,
        quality_question,
        no_label,
        yes_label,
        ready_text,
        pain_label,
        intensity_question,
        intensity_scale,
        intensity_instruction,
    )


def show_break_review(
    win,
    title,
    message,
    threshold=None,
    minimum=None,
    maximum=None,
    language="en",
    value_label="threshold",
    automatic_mode=False,
    subject="unknown",
    phase="break",
    trial_number="",
):
    """Show a participant break screen and handle experimenter review in terminal."""
    from .participant_controls import get_participant_controls

    if language not in {"en", "it"}:
        raise ValueError("language must be 'en' or 'it'.")
    if threshold is not None and (
        minimum is None or maximum is None or minimum > maximum
    ):
        raise ValueError("A valid minimum/maximum range is required for overrides.")

    text = visual.TextStim(
        win,
        text=participant_text("break", language),
        color=TEXT_COLOR,
        colorSpace="rgb255",
        height=_scaled_font_size(fontsize),
        wrapWidth=_scaled_font_size(1000),
        font=font_type,
    )
    controls = get_participant_controls(win, subject, language)
    controls.set_context(phase, trial_number)
    while True:
        text.draw()
        controls.draw()
        win.flip()
        keys = event.waitKeys(keyList=["return", "escape", "o", "e"])
        try:
            controls.process_keys(keys)
        except KeyboardInterrupt:
            return False, None
        if "escape" in keys:
            return False, None
        if "return" in keys:
            break
    if automatic_mode:
        print(f"Automatic mode: experimenter review skipped after {title}.")
        return True, threshold

    while True:
        options = "ENTER: continue, Q: stop"
        if threshold is not None:
            options += f", M: enter a manual {value_label}"
        choice = input(
            f"\nExperimenter review — {title}\n{message}\n"
            f"{options}: "
        ).strip().lower()
        if choice in {"q", "quit", "stop"}:
            return False, None
        if choice in {"", "enter", "space"}:
            return True, threshold
        if choice == "m" and threshold is not None:
            while True:
                raw_value = input(
                    f"Enter {value_label} ({minimum:.3f}–{maximum:.3f}), "
                    "or press ENTER to keep the estimate: "
                ).strip()
                if not raw_value:
                    break
                try:
                    selected = float(raw_value)
                except ValueError:
                    print("Enter a valid number.")
                    continue
                if not math.isfinite(selected) or not minimum <= selected <= maximum:
                    print(
                        f"{value_label.capitalize()} must be between {minimum:.3f} "
                        f"and {maximum:.3f}."
                    )
                    continue
                return True, selected
        else:
            print(f"Choose ENTER to continue, Q to stop, or M to set {value_label}.")


def run_participant_practice(display, subject, language="en", mode="annoyance"):
    """Practice response keys without delivering a vibration.

    mode="annoyance": pain question, plus the E (stop) and O (orgasm) keys.
    mode="pleasure": announces that the question changed, then practises
    the pleasure Yes/No answers.
    """
    if language not in {"en", "it"}:
        raise ValueError("language must be 'en' or 'it'.")
    if mode not in {"annoyance", "pleasure"}:
        raise ValueError("mode must be 'annoyance' or 'pleasure'.")
    from .participant_controls import get_participant_controls

    (
        win,
        fixation,
        _quality,
        quality_question,
        no_label,
        yes_label,
        _ready_text,
        pain_label,
        intensity_question,
        intensity_scale,
        intensity_instruction,
    ) = display
    controls = get_participant_controls(win, subject, language)
    controls.set_context(f"{mode} practice", "")
    # Same look as the real trials (run_trial): neutral white labels.
    no_label.color = "linen"
    yes_label.color = "linen"
    pain_label.color = "linen"
    show_pain_option = mode == "pleasure"
    original_question = quality_question.text
    quality_question.text = participant_text(f"{mode}_question", language)
    text = visual.TextStim(
        win,
        text="",
        color=TEXT_COLOR,
        colorSpace="rgb255",
        height=_scaled_font_size(fontsize),
        wrapWidth=_scaled_font_size(1800),
        font=font_type,
        pos=(0, +350),
    )
    copy = {
        "en": {
            "correct": "Correct. Press ENTER to continue.",
            "wrong_quit": (
                "To stop the experiment, press E. Press ENTER to try again."
            ),
            "wrong_pain_yes": (
                "To report that the vibration was annoying or painful, press "
                "RIGHT. Press ENTER to try again."
            ),
            "wrong_pain_no": (
                "If the vibration was not annoying or painful, report No "
                "with LEFT. Press ENTER to try again."
            ),
            "pain_down": (
                "Imagine the vibration was painful or annoying, but you "
                "want to continue. Which key should you press?"
            ),
            "wrong_pain_down": (
                "To report pain or annoyance without stopping the "
                "experiment, press DOWN. Press ENTER to try again."
            ),
            "wrong_yes": (
                "To report a pleasurable sensation, press RIGHT. "
                "Press ENTER to try again."
            ),
            "wrong_no": (
                "If you felt a vibration but no pleasure, report No with "
                "LEFT. Press ENTER to try again."
            ),
            "wrong_orgasm": (
                "Press O to pause and report an orgasm; then press S to "
                "resume. Press ENTER to try again."
            ),
            "pain_yes": (
                "Imagine the vibration felt annoying or painful, but you "
                "want to continue. Which key should you press?"
            ),
            "pain_no": (
                "Imagine you felt the vibration, but it was not annoying or "
                "painful. Which key should you press?"
            ),
            "pain_quit": (
                "Imagine you felt pain and want to stop the experiment. "
                "Which key should you press?"
            ),
            "pleasure_intro": (
                "The question has changed.\n\n"
                "From now on, after each vibration you will be asked whether "
                "you felt a PLEASURABLE sensation, not whether it was "
                "painful.\n\n"
                "← LEFT = No          RIGHT = Yes →\n"
                "↓ DOWN = painful or annoying (the experiment continues)\n\n"
                "Let's practise. Press ENTER to continue."
            ),
            "pleasure_yes": (
                "Imagine you felt pleasure after this trial. Which key "
                "should you press?"
            ),
            "vibration_no": (
                "Imagine you felt a vibration, but it was not pleasurable. "
                "Which key reports No?"
            ),
            "orgasm": (
                "Imagine you are having an orgasm. Press O to pause the "
                "experiment, then press S to resume."
            ),
            "complete": "Practice complete. Press ENTER to continue.",
        },
        "it": {
            "correct": "Esatto. Premi INVIO per continuare.",
            "wrong_quit": (
                "Per interrompere l'esperimento, premi E. Premi INVIO per "
                "riprovare."
            ),
            "wrong_pain_yes": (
                "Per indicare che la vibrazione è stata fastidiosa o "
                "dolorosa, premi DESTRA. Premi INVIO per riprovare."
            ),
            "wrong_pain_no": (
                "Se la vibrazione non è stata fastidiosa o dolorosa, indica "
                "No con SINISTRA. Premi INVIO per riprovare."
            ),
            "pain_down": (
                "Immagina che la vibrazione sia stata dolorosa o fastidiosa, "
                "ma di voler continuare. Quale tasto devi premere?"
            ),
            "wrong_pain_down": (
                "Per segnalare dolore o fastidio senza interrompere "
                "l'esperimento, premi GIÙ. Premi INVIO per riprovare."
            ),
            "wrong_yes": (
                "Per indicare una sensazione piacevole, premi DESTRA. "
                "Premi INVIO per riprovare."
            ),
            "wrong_no": (
                "Se hai sentito una vibrazione ma non piacere, indica No "
                "con SINISTRA. Premi INVIO per riprovare."
            ),
            "wrong_orgasm": (
                "Premi O per mettere in pausa e segnalare un orgasmo; poi "
                "premi S per riprendere. Premi INVIO per riprovare."
            ),
            "pain_yes": (
                "Immagina che la vibrazione sia stata fastidiosa o dolorosa, "
                "ma di voler continuare. Quale tasto devi premere?"
            ),
            "pain_no": (
                "Immagina di aver sentito la vibrazione, ma che non sia stata "
                "fastidiosa o dolorosa. Quale tasto devi premere?"
            ),
            "pain_quit": (
                "Immagina di aver provato dolore e di voler interrompere "
                "l'esperimento. Quale tasto devi premere?"
            ),
            "pleasure_intro": (
                "La domanda è cambiata.\n\n"
                "D'ora in poi, dopo ogni vibrazione ti verrà chiesto se hai "
                "provato una sensazione PIACEVOLE, non se è stata "
                "dolorosa.\n\n"
                "← SINISTRA = No          DESTRA = Sì →\n"
                "↓ GIÙ = dolorosa o fastidiosa (l'esperimento continua)\n\n"
                "Facciamo una prova. Premi INVIO per continuare."
            ),
            "pleasure_yes": (
                "Immagina di aver provato piacere dopo questa prova. Quale "
                "tasto devi premere?"
            ),
            "vibration_no": (
                "Immagina di aver sentito una vibrazione, ma non una "
                "sensazione piacevole. Quale tasto devi premere?"
            ),
            "orgasm": (
                "Immagina di avere un orgasmo. Premi O per mettere in pausa "
                "l'esperimento, poi premi S per riprendere."
            ),
            "complete": "Esercitazione completata. Premi INVIO per continuare all'esperimento principale.",
        },
    }[language]

    def show(message, pos=(0, 350)):
        text.text = message
        text.italic = False
        text.pos = pos
        text.draw()
        controls.draw()
        win.flip()

    def show_response_practice(message):
        text.text = message
        text.pos = (0, 350)
        # "Imagine ..." prompts in italics, to set them apart from the task.
        text.italic = True
        text.draw()
        quality_question.draw()
        no_label.draw()
        yes_label.draw()
        if show_pain_option:
            pain_label.draw()
        controls.draw()
        win.flip()

    def continue_after_feedback(message, pos=(0, 350)):
        while True:
            show(message, pos)
            keys = event.waitKeys(
                keyList=["return", "space", "escape", "e", "o"]
            )
            normalized = {str(key).lower() for key in keys}
            # Practice: E never ends the session; Escape is the
            # experimenter's emergency stop.
            if "escape" in normalized:
                controls.process_keys(["escape"], fixation=fixation)
            if "o" in normalized:
                controls.practice_orgasm_pause(fixation=fixation)
            if normalized.intersection({"return", "space"}):
                return

    def ask_key(question, expected, retry_message):
        while True:
            show_response_practice(question)
            keys = event.waitKeys(
                keyList=["left", "right", "down", "o", "e", "escape"]
            )
            normalized = {str(key).lower() for key in keys}
            if expected in normalized:
                if expected == "o":
                    controls.practice_orgasm_pause(fixation=fixation)
                continue_after_feedback(copy["correct"])
                return
            if "o" in normalized:
                controls.practice_orgasm_pause(fixation=fixation)
                continue
            if "escape" in normalized:
                controls.process_keys(["escape"], fixation=fixation)
            # A wrong key (including E) only shows the retry message.
            continue_after_feedback(retry_message)

    try:
        if mode == "annoyance":
            ask_key(copy["pain_yes"], "right", copy["wrong_pain_yes"])
            ask_key(copy["pain_no"], "left", copy["wrong_pain_no"])
            ask_key(copy["pain_quit"], "e", copy["wrong_quit"])
            ask_key(copy["orgasm"], "o", copy["wrong_orgasm"])
        else:
            continue_after_feedback(copy["pleasure_intro"], pos=(0, 0))
            ask_key(copy["pleasure_yes"], "right", copy["wrong_yes"])
            ask_key(copy["vibration_no"], "left", copy["wrong_no"])
            ask_key(copy["pain_down"], "down", copy["wrong_pain_down"])
        continue_after_feedback(copy["complete"])
    finally:
        quality_question.text = original_question


def run_vas_practice(display, subject, language="en"):
    """Practice vibration-intensity ratings when the VAS is introduced."""
    if language not in {"en", "it"}:
        raise ValueError("language must be 'en' or 'it'.")
    from .participant_controls import get_participant_controls

    (
        win,
        fixation,
        _quality,
        _quality_question,
        _no_label,
        _yes_label,
        _ready_text,
        _pain_label,
        intensity_question,
        intensity_scale,
        intensity_instruction,
    ) = display
    controls = get_participant_controls(win, subject, language)
    controls.set_context("VAS practice", "")
    copy = {
        "en": {
            "intro": (
                "From now on, after the Yes/No answer you will also rate how "
                "INTENSE the vibration was (not how pleasurable).\n\n"
                "Use LEFT/RIGHT to move the marker and UP to confirm.\n\n"
                "Let's practise. Press ENTER to continue."
            ),
            "strong": (
                "Imagine a very strong vibration that was not pleasurable. "
                "Rate vibration intensity, not pleasure."
            ),
            "faint": (
                "Imagine a very faint vibration that was pleasurable. "
                "Rate vibration intensity, not pleasure."
            ),
            "recorded": "Recorded value: {rating}/100. Press ENTER to continue.",
            "retry": (
                "The strong vibration should have a higher intensity rating "
                "than the faint vibration, regardless of pleasure. The scale "
                "measures vibration intensity, not pleasure. Press ENTER to "
                "practise both ratings again."
            ),
            "complete": "Practice complete. Press ENTER to continue.",
        },
        "it": {
            "intro": (
                "D'ora in poi, dopo la risposta Sì/No valuterai anche quanto "
                "è stata INTENSA la vibrazione (non quanto è stata "
                "piacevole).\n\n"
                "Usa SINISTRA/DESTRA per muovere il cursore e SU per "
                "confermare.\n\n"
                "Facciamo una prova. Premi INVIO per continuare."
            ),
            "strong": (
                "Immagina una vibrazione molto forte ma non piacevole. "
                "Valuta l'intensità della vibrazione, non il piacere."
            ),
            "faint": (
                "Immagina una vibrazione molto lieve ma piacevole. "
                "Valuta l'intensità della vibrazione, non il piacere."
            ),
            "recorded": "Valore registrato: {rating}/100. Premi INVIO per continuare.",
            "retry": (
                "La vibrazione forte dovrebbe avere un valore di intensità "
                "maggiore rispetto a quella lieve, indipendentemente dal "
                "piacere. La scala misura l'intensità della vibrazione, non "
                "il piacere. Premi INVIO per riprovare entrambe le valutazioni."
            ),
            "complete": "Esercitazione completata. Premi INVIO per continuare.",
        },
    }[language]
    feedback = visual.TextStim(
        win,
        text="",
        color=TEXT_COLOR,
        colorSpace="rgb255",
        height=_scaled_font_size(fontsize),
        wrapWidth=_scaled_font_size(1800),
        font=font_type,
    )

    def wait_for_enter(message):
        feedback.text = message
        while True:
            feedback.draw()
            controls.draw()
            win.flip()
            keys = event.waitKeys(
                keyList=["return", "space", "e", "o", "escape"]
            )
            normalized = {str(key).lower() for key in keys}
            # Practice: E never ends the session; Escape still aborts.
            if "escape" in normalized:
                controls.process_keys(["escape"], fixation=fixation)
            if "o" in normalized:
                controls.practice_orgasm_pause(fixation=fixation)
            if normalized.intersection({"return", "space"}):
                return

    def rate_vibration(question, trial_number):
        # "Imagine ..." prompt in italics; restored for the real trials.
        intensity_question.italic = True
        try:
            return _rate_vibration(question, trial_number)
        finally:
            intensity_question.italic = False

    def _rate_vibration(question, trial_number):
        controls.set_context("VAS practice", trial_number)
        rating = 0
        intensity_scale.reset()
        intensity_scale.setRating(rating)
        while True:
            intensity_question.text = question
            intensity_question.draw()
            intensity_scale.draw()
            intensity_instruction.draw()
            controls.draw()
            win.flip()
            keys = event.waitKeys(
                keyList=["left", "right", "up", "o", "e", "escape"]
            )
            normalized = {str(key).lower() for key in keys}
            # Practice: E never ends the session; Escape still aborts.
            if "escape" in normalized:
                controls.process_keys(["escape"], fixation=fixation)
            if "o" in normalized:
                controls.practice_orgasm_pause(fixation=fixation)
            if "left" in normalized:
                rating = max(0, rating - 1)
                intensity_scale.setRating(rating)
            elif "right" in normalized:
                rating = min(100, rating + 1)
                intensity_scale.setRating(rating)
            elif "up" in normalized:
                return rating

    wait_for_enter(copy["intro"])
    while True:
        strong_rating = rate_vibration(copy["strong"], 1)
        wait_for_enter(copy["recorded"].format(rating=strong_rating))
        faint_rating = rate_vibration(copy["faint"], 2)
        wait_for_enter(copy["recorded"].format(rating=faint_rating))
        if strong_rating > faint_rating:
            break
        wait_for_enter(copy["retry"])
    wait_for_enter(copy["complete"])