import pyaudio
import numpy as np
import PySimpleGUI as sg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

# Stream data
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 2048

# VARS CONSTS:
_VARS = {'window': False,
         'stream': False,
         'audioData': np.array([])}
         
layout = [
    [
        sg.B('Start', key='start'), 
        sg.B('Stop', key='stop', disabled=True)
    ],[
        sg.Slider(orientation ='horizontal', key='ax1y', range=(1,100)),
        sg.Slider(orientation ='horizontal', key='ax2y',range=(1,100))
    ],[
        sg.Canvas(key='controls_cv')
    ],[
        sg.Column(
            layout=[[sg.Canvas(key='fig_cv',size=(1000, 700))]],
            background_color='#DAE0E6',
            pad=(0, 0))
    ],
]

def start():
    _VARS['stream'] = pyaudio.PyAudio().open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK, stream_callback=callback)
    _VARS['stream'].start_stream()
    _VARS['window']['start'].Update(disabled=True)
    _VARS['window']['stop'].Update(disabled=False)
    
def stop():
    if _VARS['stream']:
        _VARS['stream'].stop_stream()
        _VARS['stream'].close()
    _VARS['window']['start'].Update(disabled=False)
    _VARS['window']['stop'].Update(disabled=True)
    
def callback(in_data, frame_count, time_info, status):
    _VARS['audioData'] = np.frombuffer(in_data, dtype=np.int16)
    return (in_data, pyaudio.paContinue)

def drawFig(canvas, figure):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg
    
def updateUI():
    print(".")
    # clear previous
    ax1.cla()
    ax2.cla()
    
    # get current
    data = _VARS['audioData'];
    
    # plot
    ax1.plot(data);
    ax1.axis(0, sizeof(data), -int(_VARS['window']['ax1y']), int(_VARS['window']['ax1y']))

_VARS['window'] = sg.Window('window', layout, finalize=True)
fig = plt.figure(figsize=(10,8))
ax1 = fig.add_subplot(211)
ax2 = fig.add_subplot(212)
drawFig(_VARS['window']['fig_cv'].TKCanvas, fig)

while True:
    event, values = _VARS['window'].read()
    print(event, values)
    if event == sg.WIN_CLOSED:
        break
    elif event == 'start':
        start()
    elif event == 'stop':
        stop()
    elif _VARS['audioData'].size != 0:
        updateUI()
        
_VARS['window'].close()
