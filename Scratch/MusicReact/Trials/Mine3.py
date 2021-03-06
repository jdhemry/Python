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
import math
import pygame

# VARS CONSTS:
_VARS = {'window': False,
         'stream': False,
         'listening': False,
         'paused': False,
         'buffer': [],
         'beat' : 0
        }
         
OCTAVES     = 8
NOTES       = 12
A1          = 27.
NoteStep    = 1.05946274243761
RATE        = 44100  # Equivalent to Human Hearing at 40 kHz
SaveFolder  = 'saves'
Chunk       = 512
Beats       = 64
fftOcts     = 3

pAud = pyaudio.PyAudio()
lock = threading.Lock()

Buckets     = OCTAVES * NOTES
NoteFreqs   = [0] * Buckets
NoteIntensities = [0] * Buckets
EQ = [1] * Buckets
beatTriggers = [1,2,4,8,16,32]

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
    [sg.Checkbox('Avg Filter', key='avg_chk', default=False)],
    [sg.HorizontalSeparator()],
    [sg.Text('FFT Data Plot', font=AppFont)],
    [sg.Text('Y Axis:'), sg.Slider(orientation ='horizontal', key='ax2y', range=(10**2,10**4), default_value=3000)],
    [sg.Text('Filter:'), sg.Slider(orientation ='horizontal', key='ax2_filter', range=(0,250), default_value=0)],
    [sg.HorizontalSeparator()],
    [sg.Text('Note Plot', font=AppFont)],
    [sg.Text('Z Axis Max:'), sg.Slider(orientation ='horizontal', key='ax3z', range=(0,50000), default_value=25000)],
    [sg.Text('Z Axis Max:'), sg.Slider(orientation ='horizontal', key='ax4z', range=(0,50000), default_value=0)],
    [sg.HorizontalSeparator()],
    [sg.Text('Equalizer', font=AppFont)],
    [sg.Checkbox('EQ On:', key='eq_on', default=True)],
    [sg.Slider(orientation ='vertical', key='eq1', range=(-100,100), default_value=-8),
    sg.Slider(orientation ='vertical', key='eq2', range=(-100,100), default_value=2),
    sg.Slider(orientation ='vertical', key='eq3', range=(-100,100), default_value=5),
    sg.Slider(orientation ='vertical', key='eq4', range=(-100,100), default_value=25),
    sg.Slider(orientation ='vertical', key='eq5', range=(-100,100), default_value=40),
    sg.Slider(orientation ='vertical', key='eq6', range=(-100,100), default_value=60),
    sg.Slider(orientation ='vertical', key='eq7', range=(-100,100), default_value=75),
    sg.Slider(orientation ='vertical', key='eq8', range=(-100,100), default_value=90)],
]

status = [
    [sg.Text('Window: ', justification='left'), sg.Text('X', key='a1')],
    [sg.Text('Time: ', justification='left'), sg.Text('X', key='a3')],
]

stretch = 20

screen_layout = [
    [
    buttons,
    #sg.Column(layout=[[sg.Canvas(key='fig_cv',size=(500, 700))]], background_color='#DAE0E6', pad=(0, 0)),
    sg.Graph((NOTES * stretch, OCTAVES * stretch), (0,0), (NOTES * stretch, OCTAVES * stretch), background_color='lightblue', key='-GRAPH-'),
    sg.VSeperator(),
    sg.Column(controls, vertical_alignment='top'),
    sg.Column(status, vertical_alignment='top')
    ]
]

_VARS['window'] = sg.Window('Sound transformations', screen_layout, finalize=True)
_VARS['window']['eq1'].bind('<ButtonRelease-1>', 'R')
_VARS['window']['eq2'].bind('<ButtonRelease-1>', 'R')
_VARS['window']['eq3'].bind('<ButtonRelease-1>', 'R')
_VARS['window']['eq4'].bind('<ButtonRelease-1>', 'R')
_VARS['window']['eq5'].bind('<ButtonRelease-1>', 'R')
_VARS['window']['eq6'].bind('<ButtonRelease-1>', 'R')
_VARS['window']['eq7'].bind('<ButtonRelease-1>', 'R')
_VARS['window']['eq8'].bind('<ButtonRelease-1>', 'R')

def stop():
    _VARS['listening'] = False;
    _VARS['window']['stop'].Update(disabled=True)
    _VARS['window']['pause'].Update(disabled=True)
    _VARS['window']['listen'].Update(disabled=False)
    _VARS['window']['chunk'].Update(disabled=False)
    if _VARS['stream']:
        _VARS['stream'].stop_stream()
        _VARS['stream'].close()

def callback(in_data, frame_count, time_info, status):
    #tic = time.perf_counter()

    # Lock before the setting of the data
    lock.acquire()
    
    _VARS['beat'] += 1
    if (_VARS['beat'] > Beats): 
        _VARS['beat'] = 1
    _VARS['buffer'].extend(np.frombuffer(in_data, dtype=np.int16))
    if (len(_VARS['buffer']) > (Chunk * Beats)):
        _VARS['buffer'] = _VARS['buffer'][Chunk:]
        
    lock.release()

    if (_VARS['beat'] in beatTriggers): threading.Thread(render(_VARS['beat']), args=(values)).start()
    
    #toc = time.perf_counter()
    #print(f"callback {toc - tic:0.4f} sec")
    
    return (in_data, pyaudio.paContinue)

def render(size):
    global NoteIntensities
    
    #tic = time.perf_counter()
    
    # depending on size, render different levels
    '''
     1 : 0    512 - 6,7,8
     2 : 1   1024 - 5,6,7    
     4 : 2   2048 - 4,5,6
     8 : 3   4096 - 3,4,5
    16 : 4   8192 - 2,3,4
    32 : 5  16384 - 1,2,3
    '''
    
    #toc = time.perf_counter()
    
    setSize = Chunk * size
    grab = _VARS['buffer'][(Chunk * Beats) - setSize:]
    if (len(grab) != setSize):
        return
    
    #print(f"render 1: {time.perf_counter() - toc:0.4f} sec")
    #toc = time.perf_counter()
    
    # Note: this doesn't show on the display as only used in figuring Notes
    xxx = getWindowing(values['fftwindow'], setSize)
    
    #print(f"render 2: {time.perf_counter() - toc:0.4f} sec")
    #toc = time.perf_counter()
    
    wind = grab * xxx
    #wind = grab * getWindowing(values['fftwindow'], setSize)
    
    #print(f"render 3: {time.perf_counter() - toc:0.4f} sec")
    #toc = time.perf_counter()
    
    n = int(math.log(size,2))
    maxFreq = NoteFreqs[((OCTAVES - n) * NOTES) - 1]
    minFreq = NoteFreqs[(OCTAVES - n - fftOcts) * NOTES]
    # print(f'size: {size} / minFreq: {minFreq} / maxFreq: {maxFreq}')
    
    #print(f"render 4: {time.perf_counter() - toc:0.4f} sec")
    #toc = time.perf_counter()
    
    # get freq data
    fftData = np.abs(np.fft.rfft(wind))
    fftFreq = np.fft.rfftfreq(setSize, 1./RATE)
    
    #print(f"render 5: {time.perf_counter() - toc:0.4f} sec")
    #toc = time.perf_counter()
    
    noteInt = setNoteBuckets(fftData, fftFreq, minFreq, maxFreq)
    
    #print(f"render 6: {time.perf_counter() - toc:0.4f} sec")
    #toc = time.perf_counter()
    
    # Lock before the setting of the data
    lock.acquire()
    
    # average for now
    NoteIntensities = ((np.array(NoteIntensities) + np.array(noteInt)) / 2).tolist()
    
    lock.release()
    
    #print(f"render 7: {time.perf_counter() - toc:0.4f} sec")
    #print(f"render full: size={size} {time.perf_counter() - tic:0.4f} sec")
    
def setNoteBuckets(fftData, fftFreq, minFreq=0, maxFreq=20000):
    noteInt = NoteIntensities[:]
    # Limit the upper/lower ranges to loop through
    minIdx = find_bucket_index(fftFreq, minFreq)
    maxIdx = find_bucket_index(fftFreq, maxFreq)
    for i in range(maxIdx - minIdx):
    #for i in range(fftData.size):
        if (fftFreq[minIdx + i] > minFreq and fftFreq[minIdx + i] < maxFreq):
            noteInt[find_bucket_index(NoteFreqs, fftFreq[minIdx + i])] = fftData[minIdx + i]
    return noteInt

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
                                frames_per_buffer=Chunk, stream_callback=callback)
    _VARS['stream'].start_stream()
    _VARS['listening'] = True;
    show_status()

def drawFig(canvas, figure):
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg
    
def updateUI2():
    #pygame.draw.rect((255,0,0), pygame.Rect(30,30,60,60), 2)
    return
    
def updateUI():
    if (_VARS['listening'] == True):
        #toc = time.perf_counter()
        
        # ==================== Graphing =================
        # plot sound data
        ax1.cla()
        ax1.grid()
        ax1.axis([0, Chunk * 2, -int(values['ax1y']), int(values['ax1y'])])
        ax1.plot(_VARS['buffer'][(Chunk * Beats) - (Chunk * 2):])
        ax1.title.set_text('Sound Data')
        
        #print(f"update 1: {time.perf_counter() - toc:0.4f} sec")
        
        #toc = time.perf_counter()
        
        # plot Note data
        ax2.cla()
        ax2.imshow(np.array(NoteIntensities).astype('int').reshape(OCTAVES,NOTES), 
            vmin=values['ax4z'], vmax=values['ax3z'], interpolation="nearest", origin="upper")
        ax2.title.set_text('Raw Note Intensity')
        
        #print(f"update 2: {time.perf_counter() - toc:0.4f} sec")
        
        #toc = time.perf_counter()
    
        equalized = (np.array(NoteIntensities) * np.array(EQ))
        
        ax3.cla()
        ax3.contourf(np.array(equalized).astype('int').reshape(OCTAVES,NOTES))
        #ax3.plot(np.array(equalized).astype('int').reshape(OCTAVES,NOTES))
        #ax3.imshow(np.array(equalized).astype('int').reshape(OCTAVES,NOTES), 
        #    vmin=values['ax4z'], vmax=values['ax3z'], interpolation="nearest", origin="upper")

        #print(f"update 3: {time.perf_counter() - toc:0.4f} sec")
        
    
def find_bucket_index(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx if array[idx] < value else idx - 1
    
def createEqualizer():
    global EQ
    
    # TODO calcs for smoother curves
    # Right no just straight lines per band
    for i in range(OCTAVES): 
        eqX = getEqValue(values['eq' + str(i+1)])
        start = i * 12
        for j in range(NOTES):
            EQ[start + j] = eqX
    
def getEqValue(band):
    return band if (band > 0) else 0 if (band == 0) else 1/abs(band)
    
def getWindowing(key, size):
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
    for i in range(len(NoteFreqs)):
        print(f'{NoteFreqs[i]} Hz : {NoteIntensities[i]}')

# INIT:
embed = _VARS['window']['-GRAPH-'].TKCanvas
os.environ['SDL_WINDOWID'] = str(embed.winfo_id())

#screen = pygame.display.set_mode((100,100))
#screen.fill(pygame.Color(255, 255, 255))

#pygame.display.init()

# TODO Working on using pygame to plot
# https://github.com/PySimpleGUI/PySimpleGUI/blob/master/DemoPrograms/Demo_PyGame_Integration.py

# TODO OR... directly use the sg.graph
https://www.pysimplegui.org/en/latest/call%20reference/#graph-element

'''
plt.ion()
fig = plt.figure(figsize=(5,10))
fig.tight_layout(pad=0.4, h_pad=4, w_pad=4)
ax1 = fig.add_subplot(311)
ax2 = fig.add_subplot(312)
ax3 = fig.add_subplot(313)
#ax4 = fig.add_subplot(314)
drawFig(_VARS['window']['fig_cv'].TKCanvas, fig)
'''
# MAIN LOOP
while True:
    event, values = _VARS['window'].read(timeout=10)
    #if event != '__TIMEOUT__': print(event, values)
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
        createEqualizer()
        listen()
    if event in ['eq1R','eq2R','eq3R','eq4R','eq5R','eq6R','eq7R']:
        createEqualizer()
    if event == 'stop':
        stop()
    else:
        updateUI2()

_VARS['window'].close()

