import PySimpleGUI as sg
import pyaudio
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import json
import os
import sys
import time
import threading

# VARS CONSTS:
_VARS = {'window': False,
         'stream': False,
         'listening': False,
         'paused': False,
         'buffer': [],
         'beat' : 0
        }
         
OCTAVES     = 7
NOTES       = 12
A1          = 54.
NoteStep    = 1.05946274243761
RATE        = 44100  # Equivalent to Human Hearing at 40 kHz
SaveFolder  = 'saves'

pAud = pyaudio.PyAudio()
lock = threading.Lock()

Buckets     = OCTAVES * NOTES
NoteFreqs   = [0] * Buckets
NoteIntensities = [0] * Buckets
beatTriggers = [2,4,8,16,32]

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
    sg.Button('Exit', key='exit', font=AppFont),
    sg.Button('Display', key='display', font=AppFont)
]

windowOptions = ['', 'Bartlett', 'Blackman', 'Hamming', 'Hanning', 'Kaiser']
controls = [
    [sg.Text('Sound Data Plot', font=AppFont)],
    [sg.Text('Y Axis:'), sg.Slider(orientation ='horizontal', key='ax1y', range=(50,1000), default_value=1000)],
    [sg.Text('Window:'), sg.Combo(windowOptions, default_value='Blackman', key='fftwindow')],
    [sg.Text('Chunk:'), sg.Slider(orientation ='horizontal', key='chunk', range=(0,8), default_value=2)],
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
    [sg.Text('Beat: ', justification='left'), sg.Text('X', key='a4')],
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

# TODO ability to change A1 -> NoteFreqs... on the fly
# TODO FFT windowing / eq... from Arduino example?
# TODO controls for (octaves, A1, ...)
# TODO Circular buffer to query diff bands? at differing speeds, grab smaller chunks for high, and longer for low
# TODO Save variables to singular storage
# TODO Clean up py file organization

# TODO Test diff microphones

# TODO Switch to input card? or audio stream?

def stop():
    _VARS['listening'] = False;
    _VARS['window']['stop'].Update(disabled=True)
    _VARS['window']['pause'].Update(disabled=True)
    _VARS['window']['listen'].Update(disabled=False)
    _VARS['window']['chunk'].Update(disabled=False)
    if _VARS['stream']:
        _VARS['stream'].stop_stream()
        _VARS['stream'].close()

maxBuffer = 2**14
chunk = 256
beats = 64

def callback(in_data, frame_count, time_info, status):
    _VARS['beat'] += 1
    if (_VARS['beat'] > beats): 
        _VARS['beat'] = 1
    _VARS['buffer'].extend(np.frombuffer(in_data, dtype=np.int16))
    if (len(_VARS['buffer']) > maxBuffer):
        _VARS['buffer'] = _VARS['buffer'][chunk:]
    if (_VARS['beat'] in beatTriggers): threading.Thread(render(_VARS['beat']), args=(values)).start()
    return (in_data, pyaudio.paContinue)

def render(size):
    global NoteIntensities
    # depending on size, render different levels
    '''
     2 :  512*2 -  - calcs for oct 5,6,7
     4 : 1024*2 -  - calcs for oct 4,5,6,7
     8 : 2048*2 -  - calcs for oct 3,4,5,6,7
    16 : 4096*2 -  - calcs for oct 2,3,4,5,6,7
    32 : 8192*2 -  - calcs for oct 1,2,3,4,5,6,7
    '''
    setSize = chunk * size
    grab = _VARS['buffer'][(chunk * beats) - setSize:]
    if (len(grab) != setSize):
        return
    #print(f'yep: grab={len(grab)}, size={size}, setSize={setSize}')
        
    # TODO avg filter using on fly created array
    wind = grab * getWindowing(values['fftwindow'], setSize)
    
    # TODO Might be a way to calc this...
    cutOctaves = 4 if size == 2 else 3 if size == 4 else 2 if size == 8 else 1 if size == 16 else 0
    #blah = (cutOctaves * NOTES) + 1
    # print(f'minFreq: blah={blah}, cutOctaves={cutOctaves}')
    minFreq = NoteFreqs[(cutOctaves*NOTES)+1]

    # get freq data
    fftData = np.abs(np.fft.rfft(wind))
    fftFreq = np.fft.rfftfreq(setSize, 1./RATE)
    
    noteInt = setNoteBuckets(fftData, fftFreq, minFreq)
    
    # Lock before the setting of the data
    lock.acquire()
    
    # average for now
    NoteIntensities = ((np.array(NoteIntensities) + np.array(noteInt)) / 2).tolist()
    
    lock.release()

def setNoteBuckets(fftData, fftFreq, minFreq=0):
    noteInt = NoteIntensities[:]
    # Limit the upper/lower ranges to loop through
    for i in range(fftData.size):
        if (fftFreq[i] > minFreq):
            noteInt[find_bucket_index(NoteFreqs, fftFreq[i])] = fftData[i]
    return noteInt

def getDataSize():
    return int(64 * chunk)

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
                                frames_per_buffer=chunk, stream_callback=callback)
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
        
        _VARS['window']['a4'].update(_VARS['beat'])

        # ==================== Graphing =================
        # plot sound data
        ax1.cla()
        ax1.grid()
        ax1.axis([0, chunk * 4, -int(values['ax1y']), int(values['ax1y'])])
        ax1.plot(_VARS['buffer'][maxBuffer - (chunk * 4):])

        # plot Note data
        ax3.cla()
        ax3.imshow(np.array(NoteIntensities).reshape(OCTAVES,NOTES), interpolation="nearest", origin="upper")

def find_bucket_index(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx if array[idx] < value else idx - 1
   
def getWindowing(key, size=getDataSize()):
    if (key == "Bartlett"):
        return np.bartlett(size)
    elif (key == "Blackman"):
        return np.blackman(size)
    elif (key == "Hamming"):
        return np.hamming(size)
    elif (key == "Hanning"):
        return np.hanning(size)
    elif (key == "Kaiser"):
        return np.kaiser(size, 5)
    else:
        return np.ones(size)

def show_status():
    _VARS['window']['a1'].update(values['fftwindow'])
    _VARS['window']['a2'].update(getDataSize())

def save():
    filename =  sg.PopupGetFile('Enter File Name:', save_as=True)
    if (filename):
        with open(SaveFolder + '/' + filename + '.dat', 'w') as filehandle:
            json.dump(_VARS['buffer'].tolist(), filehandle)

def load():
    filename = sg.popup_get_file('File Select')
    if (filename):
        with open(filename, 'r') as file:
            _VARS['buffer'] = np.array(json.load(file))
        _VARS['listening'] = True
        # TODO also need to set a bunch of stuff here? disables and such
        
def display():
    print(NoteIntensities)

# INIT:
plt.ion()
fig = plt.figure(figsize=(5,8))
ax1 = fig.add_subplot(311)
#ax2 = fig.add_subplot(312)
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
    if event == 'display':
        display()
    if event == 'save':
        save()
    if event == 'listen':
        listen()
    if event == 'stop':
        stop()
    else:
        updateUI()

_VARS['window'].close()

