import PySimpleGUI as sg
import pyaudio
import numpy as np

""" RealTime PyAudio wave plot & FFT Transform """

# VARS CONSTS:
_VARS = {'window': False,
         'stream': False,
         'audioData': np.array([])}

# pysimpleGUI INIT:
AppFont = 'Any 16'
sg.theme('TealMono')
CanvasSizeWH = 500

layout = [[sg.Graph(canvas_size=(CanvasSizeWH, CanvasSizeWH),
                    graph_bottom_left=(-16, -16),
                    graph_top_right=(116, 116),
                    background_color='#FFF9DE',
                    key='graph')],
          [sg.ProgressBar(4000, orientation='h',
                          size=(20, 20), key='-PROG-')],
          [sg.Button('Listen', font=AppFont),
           sg.Button('Stop', font=AppFont, disabled=True),
           sg.Button('Exit', font=AppFont)]]
_VARS['window'] = sg.Window('Pyaudio Wave plot + FFT',
                            layout, finalize=True)

graph = _VARS['window']['graph']

# INIT vars:
CHUNK = 1024  # Samples: 1024,  512, 256, 128
RATE = 44100  # Equivalent to Human Hearing at 40 kHz
INTERVAL = 1  # Sampling Interval in Seconds ie Interval to listen
TIMEOUT = 10  # In ms for the event loop
GAIN = 0.6
pAud = pyaudio.PyAudio()

# FUNCTIONS:


def drawAxis():
    graph.DrawLine((0, 50), (100, 50))  # Y Axis
    graph.DrawLine((0, 0), (0, 100))  # X Axis


def drawTicks():

    divisionsX = 12
    multi = int(RATE/divisionsX)
    offsetX = int(100/divisionsX)

    divisionsY = 10
    offsetY = int(100/divisionsY)

    for x in range(0, divisionsX+1):
        # print('x:', x)
        graph.DrawLine((x*offsetX, -3), (x*offsetX, 3))
        graph.DrawText(int((x*multi/1000)), (x*offsetX, -10), color='black')

    for y in range(0, divisionsY+1):
        graph.DrawLine((-3, y*offsetY), (3, y*offsetY))


def drawAxesLabels():
    graph.DrawText('kHz', (50, 10), color='black')
    graph.DrawText('Freq. Level - Amplitude', (-5, 50),
                   color='black', angle=90)


def drawPlot():
    # Divide horizontal axis space by data points :
    barStep = 100/CHUNK
    x_scaled = ((_VARS['audioData']/100)*GAIN)+50

    for i, x in enumerate(x_scaled):
        graph.draw_rectangle(top_left=(i*barStep, x),
                             bottom_right=(i*barStep+barStep, 50),
                             fill_color='lightblue')


def drawFFT():
    barStep = 100/(CHUNK/2)
    fft_data = np.fft.rfft(_VARS['audioData'])
    fft_data = np.absolute(fft_data)
    fft_data = fft_data/6000

    for i, x in enumerate(fft_data):
        graph.draw_rectangle(top_left=(i*barStep, x),
                             bottom_right=(i*barStep+barStep, 0),
                             fill_color='#FF4646')

# PYAUDIO STREAM :


def stop():
    if _VARS['stream']:
        _VARS['stream'].stop_stream()
        _VARS['stream'].close()
        _VARS['window']['-PROG-'].update(0)
        _VARS['window'].FindElement('Stop').Update(disabled=True)
        _VARS['window'].FindElement('Listen').Update(disabled=False)


def callback(in_data, frame_count, time_info, status):
    _VARS['audioData'] = np.frombuffer(in_data, dtype=np.int16)
    return (in_data, pyaudio.paContinue)


def listen():
    _VARS['window'].FindElement('Stop').Update(disabled=False)
    _VARS['window'].FindElement('Listen').Update(disabled=True)
    _VARS['stream'] = pAud.open(format=pyaudio.paInt16,
                                channels=1,
                                rate=RATE,
                                input=True,
                                frames_per_buffer=CHUNK,
                                stream_callback=callback)
    _VARS['stream'].start_stream()


def updateUI():
    # Uodate volumne meter
    _VARS['window']['-PROG-'].update(np.amax(_VARS['audioData']))
    # Redraw plot
    graph.erase()
    drawAxis()
    drawTicks()
    drawAxesLabels()
    drawPlot()
    drawFFT()


# INIT:
drawAxis()
drawTicks()
drawAxesLabels()

# MAIN LOOP
while True:
    event, values = _VARS['window'].read(timeout=TIMEOUT)
    if event == sg.WIN_CLOSED or event == 'Exit':
        stop()
        pAud.terminate()
        break
    if event == 'Listen':
        listen()
    if event == 'Stop':
    	stop()
