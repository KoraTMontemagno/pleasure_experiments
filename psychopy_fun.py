from psychopy import core, event, monitors, visual

# Create a monitor (optional, avoids warnings)
#mon = monitors.Monitor("testMonitor", width=30, distance=60)  # Width in cm, Distance in cm

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

    return win, fixation, quality, quality_question, no_label, yes_label