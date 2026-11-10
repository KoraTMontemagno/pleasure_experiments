from psychopy import core, event, monitors, visual

fontsize = 60
# Create a monitor (optional, avoids warnings)
#mon = monitors.Monitor("testMonitor", width=30, distance=60)  # Width in cm, Distance in cm

def psycho_stuff_dolore():
    # Full screen?
    Full_screen = True
    
    # Create a PsychoPy window
    win = visual.Window(
    #    size= (500, 500),
        color=(5,1,74), #darkblue
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
        color='white',
        height=100,
        pos=(0, 0)
    )
    
    quality_question = visual.TextStim(
        win,
        text='Hai provato una sensazione di fastidio intenso/dolore? \n',
        color='white',
        height=fontsize,
        pos=(0, +200),
        font = "Times New Roman"
    )

    no_label = visual.TextStim(
    win, text="←\nNo", pos=(-300, -100), color='white', height=60, font = "Times New Roman",
    )
    yes_label = visual.TextStim(
    win, text="→\nSì", pos=(300, -100), color='white', height=60, font = "Times New Roman",
    )
    pain_label = visual.TextStim(
        win, text="↓\nLa sensazione è fastidiosa/dolorosa", pos=(300, -400), color='white', height=60, font = "Times New Roman",
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
        labelColor='White',
        labelHeight=0.4,
        markerColor='blue',
        font = "Times New Roman",
        colorSpace="rgb255",
        lineColor = (5,1,74),
    )
    # Hide the line by making its color match background
    #quality.marker.size = (0.01*2, 0.03*2)

    ready_text = visual.TextStim(
        win,
        text="""
In questa parte dell'esperimento, riceverai delle vibrazioni sulla clitoride.\n\n
Siccome ognun* risponde al piacere in modo soggettivo, vogliamo capire quali intensità di vibrazione preferisci, e quali evitare. \n
Per questo, ti chiediamo di dirci quando la sensazione che ricevi diventa fastidiosa/dolorosa, così da evitare quelle intensità nella prossima parte dell'esperimento.
Utilizza le freccette sulla tastiera per rispondere Sì/No (sinistra/destra, le vedrai sullo schermo).
""",
        color='white',
        height=fontsize,
        wrapWidth=1500,
        font= "Times New roman"
    )

    return win, fixation, quality, quality_question, no_label, yes_label, ready_text, pain_label

def psycho_stuff_piacere():
    # Full screen?
    Full_screen = True
    
    # Create a PsychoPy window
    win = visual.Window(
    #    size= (500, 500),
        color=(5,1,74), #darkblue
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
        color='white',
        height=100,
        pos=(0, 0)
    )
    
    quality_question = visual.TextStim(
        win,
        text='Hai provato una sensazione piacevole? \n',
        color='white',
        height=fontsize,
        pos=(0, +200),
        font = "Times New Roman"
    )

    no_label = visual.TextStim(
    win, text="←\nNo, né piacevole, né fastidiosa", pos=(-300, -100), color='white', height=60, font = "Times New Roman",
    )
    yes_label = visual.TextStim(
    win, text="→\nSì, piacevole", pos=(300, -100), color='white', height=60, font = "Times New Roman",
    )

    pain_label = visual.TextStim(
    win, text="↓\nLa sensazione è fastidiosa/dolorosa", pos=(300, -400), color='white', height=60, font = "Times New Roman",
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
        labelColor='White',
        labelHeight=0.4,
        markerColor='blue',
        font = "Times New Roman",
        colorSpace="rgb255",
        lineColor = (5,1,74),
    )
    # Hide the line by making its color match background
    #quality.marker.size = (0.01*2, 0.03*2)

    ready_text = visual.TextStim(
        win,
        text="""
Anche in questa parte dell'esperimento riceverai delle vibrazioni sulla clitoride.\n\n
Questa volta, vogliamo capire quali intensità di vibrazione sono per te le più piacevoli \n
Per questo, ti chiediamo di dirci quando la sensazione che ricevi diventa piacevole. \n
Utilizza le freccette sulla tastiera per rispondere Sì/No (sinistra/destra, le vedrai sullo schermo). \n
Se la sensazione diventa dolorosa/fastidiosa, indicala con la freccia in basso (vedrai anche questa sullo schermo)

""",
        color='white',
        height=fontsize,
        wrapWidth=1500,
        font= "Times New roman"
    )

    return win, fixation, quality, quality_question, no_label, yes_label, ready_text, pain_label


def psycho_stuff():
    # Full screen?
    Full_screen = True
    
    # Create a PsychoPy window
    win = visual.Window(
    #    size= (500, 500),
        color=(5,1,74), #darkblue
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
        color='white',
        height=80,
        pos=(0, 0)
    )
    
    quality_question = visual.TextStim(
        win,
        text='Did you feel a pleasurable sensation?',
        color='white',
        height=50,
        pos=(0, +200),
        font = "Times New Roman"
    )

    no_label = visual.TextStim(
    win, text="←\nNo", pos=(-300, -100), color='white', height=60, font = "Times New Roman",
    )
    yes_label = visual.TextStim(
    win, text="→\nYes", pos=(300, -100), color='white', height=60, font = "Times New Roman",
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
        labelColor='White',
        labelHeight=0.4,
        markerColor='blue',
        font = "Times New Roman",
        colorSpace="rgb255",
        lineColor = (5,1,74),
    )
    # Hide the line by making its color match background
    #quality.marker.size = (0.01*2, 0.03*2)

    ready_text = visual.TextStim(
        win,
        text="You will receive some vibration stimuli. After each stimulus you will be asked whether it was pleasurable or not - use your left and right arrow on the keyboard to answer.\n Are you ready?\n\nPress SPACE or ENTER to start.",
        color='white',
        height=60,
        wrapWidth=1000,
        font= "Times New roman"
    )

    return win, fixation, quality, quality_question, no_label, yes_label, ready_text