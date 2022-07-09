import PySimpleGUI as sg
import pyaudio
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

# VARS CONSTS:
_VARS = {'window': False,
         'stream': False,
         'audioData': np.array([]),
         'listening': False}
         
OCTAVES     = 7
NOTES       = 12
A1          = 54.
NoteStep    = 1.05946274243761
Filter      = 50
RATE        = 44100  # Equivalent to Human Hearing at 40 kHz

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

layout = [[sg.Column(
            layout=[[sg.Canvas(key='fig_cv',size=(1000, 700))]],
            background_color='#DAE0E6',
            pad=(0, 0))],
          [sg.Button('Listen', key='listen', font=AppFont),
           sg.Button('Stop', key='stop', font=AppFont, disabled=True),
           sg.Button('Exit', key='exit', font=AppFont)],
          [sg.Slider(orientation ='horizontal', key='ax1y', range=(20,500), default_value=250),
           sg.Slider(orientation ='horizontal', key='ax2y', range=(10**2,10**4), default_value=3000),
           sg.Slider(orientation ='horizontal', key='chunk', range=(0,6), default_value=4)],
          [sg.Combo(['', 'Bartlett', 'Blackman', 'Hamming', 'Hanning', 'Kaiser'], 
                default_value='Blackman', key='fftwindow')],
          [sg.Checkbox('Avg Filter', key='avg_chk', default=True)]]

_VARS['window'] = sg.Window('Mic to waveform plot + Max Level', layout, finalize=True)

# TODO Limit the Freq graph to human hearing (20hz to 20Khz)
# TODO Diplay freq (approx) on graph
# TODO Show calculation times and other data
# TODO Move sliders close to axis they change
# TODO Poss to have some sort of circular buffer - can grab smaller chunks for high, and longer for low
# TODO Switch to input card? or audio stream?

def stop():
    _VARS['listening'] = False;
    _VARS['audioData'] = np.array([])
    _VARS['window']['stop'].Update(disabled=True)
    _VARS['window']['listen'].Update(disabled=False)
    _VARS['window']['chunk'].Update(disabled=False)
    #print(_VARS['audioData'].size)
    if _VARS['stream']:
        _VARS['stream'].stop_stream()
        _VARS['stream'].close()
    
def callback(in_data, frame_count, time_info, status):
    _VARS['audioData'] = np.frombuffer(in_data, dtype=np.int16)
    return (in_data, pyaudio.paContinue)

def getDataSize():
    return int(64 * (2**int(values['chunk'])))
    
def listen():
    _VARS['window']['stop'].Update(disabled=False)
    _VARS['window']['listen'].Update(disabled=True)
    _VARS['window']['chunk'].Update(disabled=True)
    
    _VARS['stream'] = pAud.open(format=pyaudio.paInt16,
                                channels=1,
                                rate=RATE,
                                input=True,
                                frames_per_buffer=getDataSize(),
                                stream_callback=callback)
    _VARS['stream'].start_stream()
    _VARS['listening'] = True;

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
        
        # Parse frequencies into buckets
        for i in range(fftData.size):
            # Test if the value is above a noise filter (or filter the array afterwards)
            if (fftData[i] > Filter):
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
        ax2.axis([0, fftData.size, 0, int(values['ax2y'])])
        ax2.plot(fftData)
        
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
        return np.array(1)

# INIT:
plt.ion()
fig = plt.figure(figsize=(10,8))
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
    if event == 'listen':
        listen()
    if event == 'stop':
        stop()
    elif _VARS['audioData'].size != 0:
        updateUI()


_VARS['window'].close()

