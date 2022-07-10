import PySimpleGUI as sg
import pyaudio
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import json
import os
import sys
import time

# VARS CONSTS:
_VARS = {'window': False,
         'stream': False,
         'audioData': np.array([]),
         'listening': False,
         'paused': False}
         
OCTAVES     = 7
NOTES       = 12
A1          = 54.
NoteStep    = 1.05946274243761
RATE        = 44100  # Equivalent to Human Hearing at 40 kHz
SaveFolder  = 'saves'

pAud = pyaudio.PyAudio()

Buckets     = OCTAVES * NOTES
NoteFreqs   = [0] * Buckets
NoteIntensities = [0] * Buckets

# Set frequencies for grid
for i in range(Buckets):
    NoteFreqs[i] = A1 * pow(NoteStep, i+3)
        
# pysimpleGUI INIT:
AppFont = 'Any 16'
sg.theme('Black')
CanvasSizeWH = 500

script_path = os.getcwd()
new_abs_path = os.path.join(script_path, 'saves')
if not os.path.exists(new_abs_path):
  os.mkdir(new_abs_path)

buttons = [
    sg.Button('Listen', key='listen', font=AppFont),
    sg.Button('Stop', key='stop', font=AppFont, disabled=True),
    sg.Button('Pause', key='pause', font=AppFont, disabled=True),
    sg.Button('Save', key='save', font=AppFont, disabled=True),
    sg.Button('Load', key='load', font=AppFont),
    sg.Button('Exit', key='exit', font=AppFont)
]

windowOptions = ['', 'Bartlett', 'Blackman', 'Hamming', 'Hanning', 'Kaiser']
controls = [
    [sg.Text('Sound Data Plot', font=AppFont)],
    [sg.Text('Y Axis:'), sg.Slider(orientation ='horizontal', key='ax1y', range=(20,500), default_value=250)],
    [sg.Text('Window:'), sg.Combo(windowOptions, default_value='Blackman', key='fftwindow')],
    [sg.Text('Chunk:'), sg.Slider(orientation ='horizontal', key='chunk', range=(0,8), default_value=4)],
    [sg.Checkbox('Avg Filter', key='avg_chk', default=True)],
    [sg.HorizontalSeparator()],
    [sg.Text('FFT Data Plot', font=AppFont)],
    [sg.Text('Y Axis:'), sg.Slider(orientation ='horizontal', key='ax2y', range=(10**2,10**4), default_value=3000)],
    [sg.Text('Filter:'), sg.Slider(orientation ='horizontal', key='ax2_filter', range=(0,250), default_value=0)],
]

status = [
    [sg.Text('Window: ', justification='left'), sg.Text('X', key='a1')],
    [sg.Text('Chunk Size: ', justification='left'), sg.Text('X', key='a2')],
    [sg.Text('Time: ', justification='left'), sg.Text('X', key='a3')],
]

screen_layout = [
    [
    buttons,
    sg.Column(layout=[[sg.Canvas(key='fig_cv',size=(500, 700))]], background_color='#DAE0E6', pad=(0, 0)),
    sg.VSeperator(),
    sg.Column(controls, vertical_alignment='top'),
    sg.Column(status, vertical_alignment='top')
    ]
]

_VARS['window'] = sg.Window('Sound transformations', screen_layout, finalize=True)

# TODO FFT windowing... from Arduino example?
# TODO controls for (octaves, A1, ...)
# TODO Circular buffer to query diff bands? at differing speeds, grab smaller chunks for high, and longer for low
# TODO Save variables to singular storage
# TODO Clean up py file organization

# TODO Test diff microphones

# TODO Switch to input card? or audio stream?

def stop():
    _VARS['listening'] = False;
    _VARS['audioData'] = np.array([])
    _VARS['window']['stop'].Update(disabled=True)
    _VARS['window']['pause'].Update(disabled=True)
    _VARS['window']['listen'].Update(disabled=False)
    _VARS['window']['chunk'].Update(disabled=False)
    if _VARS['stream']:
        _VARS['stream'].stop_stream()
        _VARS['stream'].close()
    
def callback(in_data, frame_count, time_info, status):
    _VARS['audioData'] = np.frombuffer(in_data, dtype=np.int16)
    return (in_data, pyaudio.paContinue)

def getDataSize():
    return int(64 * (2**int(values['chunk'])))

def pause():
    # leave buffer full, but stop the stream
    if (_VARS['paused']):
        _VARS['window']['save'].Update(disabled=True)
        _VARS['paused'] = False
        _VARS['stream'].start_stream()
    else:
        _VARS['window']['save'].Update(disabled=False)
        _VARS['paused'] = True
        _VARS['stream'].stop_stream()

def listen():
    _VARS['window']['stop'].Update(disabled=False)
    _VARS['window']['pause'].Update(disabled=False)
    _VARS['window']['listen'].Update(disabled=True)
    _VARS['window']['chunk'].Update(disabled=True)
    _VARS['stream'] = pAud.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True,
                                frames_per_buffer=getDataSize(), stream_callback=callback)
    _VARS['stream'].start_stream()
    _VARS['listening'] = True;
    show_status()

def drawFig(canvas, figure):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg
    
def updateUI():
    if (_VARS['listening'] == True):
        # This is an error check as it happens when changing windowing
        if (_VARS['audioData'].size != getWindowing(values['fftwindow']).size):
            return;
        
        tic = time.perf_counter()
        
        # zero out before filling
        NoteIntensities = [0] * Buckets
        
        # ================== Calculations ===============
        # multiply by window
        filtered = _VARS['audioData']
        if (_VARS['window']['avg_chk'].get()):
            filtered = filtered - np.average(_VARS['audioData'])
        windowed = filtered * getWindowing(values['fftwindow'])
        
        # get freq data
        fftData = np.abs(np.fft.rfft(windowed))
        fftFreq = np.fft.rfftfreq(getDataSize(), 1./RATE)
        
        toc = time.perf_counter()
        _VARS['window']['a3'].update(f"{toc - tic:0.4f} sec")
        
        # Parse frequencies into buckets
        for i in range(fftData.size):
            # Test if the value is above a noise filter (or filter the array afterwards)
            if (fftData[i] > values['ax2_filter']):
                idx = find_bucket_index(NoteFreqs, fftFreq[i])
                NoteIntensities[idx] = fftData[i]

        # zero out last bucket as is getting junk filled...
        NoteIntensities[len(NoteIntensities) -1] = 0
        
        # ==================== Graphing =================
        # plot sound data
        ax1.cla()
        ax1.grid()
        ax1.axis([0, windowed.size, -int(values['ax1y']), int(values['ax1y'])])
        ax1.plot(windowed)
        
        # plot fft data
        ax2.cla()
        ax2.grid()
        #ax2.axis([0, 250, 0, int(values['ax2y'])])
        ax2.plot(fftFreq, fftData)
        
        # plot Note data
        ax3.cla()
        ax3.imshow(np.array(NoteIntensities).reshape(OCTAVES,NOTES), interpolation="nearest", origin="upper")

def find_bucket_index(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx if array[idx] < value else idx - 1
   
def getWindowing(key):
    if (key == "Bartlett"):
        return np.bartlett(getDataSize())
    elif (key == "Blackman"):
        return np.blackman(getDataSize())
    elif (key == "Hamming"):
        return np.hamming(getDataSize())
    elif (key == "Hanning"):
        return np.hanning(getDataSize())
    elif (key == "Kaiser"):
        return np.kaiser(getDataSize(), 5)
    else:
        return np.ones(getDataSize())

def show_status():
    _VARS['window']['a1'].update(values['fftwindow'])
    _VARS['window']['a2'].update(getDataSize())

def save():
    filename =  sg.PopupGetFile('Enter File Name:', save_as=True)
    if (filename):
        with open(SaveFolder + '/' + filename + '.dat', 'w') as filehandle:
            json.dump(_VARS['audioData'].tolist(), filehandle)

def load():
    filename = sg.popup_get_file('File Select')
    if (filename):
        with open(filename, 'r') as file:
            _VARS['audioData'] = np.array(json.load(file))
        _VARS['listening'] = True
        # TODO also need to set a bunch of stuff here? disables and such
        
# INIT:
plt.ion()
fig = plt.figure(figsize=(5,8))
ax1 = fig.add_subplot(311)
ax2 = fig.add_subplot(312)
ax3 = fig.add_subplot(313)
drawFig(_VARS['window']['fig_cv'].TKCanvas, fig)

# MAIN LOOP
while True:
    event, values = _VARS['window'].read(timeout=10)
    #print(event, values)
    if event == sg.WIN_CLOSED or event == 'exit':
        stop()
        pAud.terminate()
        break
    if event == 'pause':
        pause()
    if event == 'load':
        load()
    if event == 'save':
        save()
    if event == 'listen':
        listen()
    if event == 'stop':
        stop()
    elif _VARS['audioData'].size != 0:
        updateUI()


_VARS['window'].close()

