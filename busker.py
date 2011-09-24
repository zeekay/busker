import itertools, random
import pypm

DEFAULT_VOLUME = 60
DEFAULT_BPM = 120

class Time(object):
    def __init__(self, bpm=None):
        self.bpm = bpm
        if bpm is None:
            self.bpm = DEFAULT_BPM
        self.quarter = self.MPQN = 60000000 / self.bpm / 1000
        self.half = self.quarter * 2
        self.whole = self.quarter * 4
        self.eigth = self.quarter * .5
        self.sixteenth = self.bpm * .25
        self.thirtysecond = self.bpm * .125
        self.sixtyfourth = self.bpm * 0.0625

DEFAULT_LENGTH = Time().quarter

def list_devices():
    print 'Devices:'
    inputs, outputs = [], []
    for i in range(pypm.CountDevices()):
        interface, name, input, output, opened = pypm.GetDeviceInfo(i)
        device = '%d [%s]' % (i, name)
        if opened == 1:
            device += ' [open]'
        if input == 1:
            inputs.append(device)
        else:
            outputs.append(device)
    print '  Input:'
    for device in inputs:
        print '    ' + device
    print '  Output:'
    for device in outputs:
        print '    ' + device

twelve_tone = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
twelve_tone_cycle = itertools.cycle(twelve_tone)
midi_notes = [(twelve_tone_cycle.next().lower(), (octave - 2)) for octave in [(x / 12) for x in range(128)]]
twelve_tone_cycle = itertools.cycle(twelve_tone)
midi_notes_joined = [twelve_tone_cycle.next().lower() + str(octave - 2) for octave in [(x / 12) for x in range(128)]]

def shift_notes(notes, offset):
    return notes[offset:] + notes[:offset]

def scale_notes(key, intervals, midi=False):
    key = midi_note(key)
    return [midi_notes_joined[y].upper() for y in [x + key for x in intervals]]
#    offset = twelve_tone.index(key)
#    notes = shift_notes(intervals, key)
#    return [notes[x] for x in intervals]

chromatic = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
diatonic = (0, 2, 4, 5, 7, 9, 11)
major = diatonic
minor = (0, 2, 3, 5, 7, 8, 10)
melodic_minor = (0, 2, 4, 5, 7, 8, 11)
harmonic_minor = (0, 2, 4, 5, 7, 8, 10)
ionian, dorian, phrygian, lydian, mixolydian, aeolian, ionian = (shift_notes(diatonic, x) for x in range(7))

def midi_note(note, octave=None):
    if type(note) is tuple:
        note = ''.join((note[0], str(note[1])))
    note = note.lower()
    if note in midi_notes_joined:
        return midi_notes_joined.index(note)
    if octave is None:
        octave = 3
    return midi_notes.index((note, octave))

def midi_chord(key, chord):
    return [midi_note(key) + (interval - 1) for interval in chord]

class Instrument(object):
    def __init__(self, id, latency=1, channel='0'):
        self.latency = latency
        self.id = id
        self.device = self.open_output()
        self.channel = channel

    def open_output(self):
        pypm.Initialize()
        return pypm.Output(self.id, self.latency)

    def send_midi(self, note, channel=None, command=None, time=None, volume=None):
        if command is None:
            command = '0x9'
        if channel is None:
            channel = self.channel
        if volume is None:
            volume = DEFAULT_VOLUME
        if time is None:
            time = pypm.Time()
        status = int(''.join((command, channel)), 16)
        self.device.Write([[[status, note, volume], time]])

    def send_multiple(self, messages):
        def fmt_msg(note, channel=None, command=None, time=None, volume=None):
            if command is None:
                command = '0x9'
            if channel is None:
                channel = self.channel
            if volume is None:
                volume = DEFAULT_VOLUME
            if time is None:
                time = pypm.Time()
            status = int(''.join((command, channel)), 16)
            return [[status, note, volume], time]
        self.device.Write([fmt_msg(*msg) for msg in messages])

    def send_sysex(self, sysex, time=None):
        if time is None:
            time = pypm.Time()
        self.device.WriteSysEx(time, sysex)

    def noteon(self, note, channel=None, time=None, volume=None):
        if type(note) == str:
            note = midi_note(note)
        self.send_midi(note, channel, '0x9', time, volume)

    def noteoff(self, note=None, channel=None, time=None):
        if note is None:
            self.send_multiple(((note, channel, '0x8', None, 0) for note in range(128)))
        else:
            if type(note) is str:
                note = midi_note(note)
            self.send_midi(note, channel, '0x8', time, 0)

    def play(self, note, channel=None, length=None, volume=None):
        if type(note) is str:
            note = midi_note(note)
        if length is None:
            length = DEFAULT_LENGTH
        self.noteon(note, channel, pypm.Time(), volume)
        self.noteoff(note, channel, pypm.Time() + length)

    def play_chord(self, chord, channel=None, length=None, volume=None):
        if isinstance(chord, Chord):
            notes = chord.midi
        elif type(chord) is str:
            notes = [midi_note(x) for x in chord.split()]
        elif type(chord) is tuple or list:
            if type(chord[0]) is str:
                notes = (midi_note(x) for x in chord)
            else:
                notes = chord
        if length is None:
            length = DEFAULT_LENGTH
        self.send_multiple([(note, channel, '0x9', None, volume) for note in notes])
        self.send_multiple([(note, channel, '0x8', length+pypm.Time(), 0) for note in notes])

    def play_arp(self, chord, arp_func, channel=None, volume=None, length=None):
        if isinstance(chord, Chord):
            notes = chord.midi
        elif type(chord) is str:
            notes = [midi_note(x) for x in chord.split()]
        elif type(chord) is tuple or list:
            if type(chord[0]) is str:
                notes = (midi_note(x) for x in chord)
            else:
                notes = chord
        if length is None:
            length = DEFAULT_LENGTH
        start, end = arp_func(notes, channel, length, volume)
        self.send_multiple(start)
        self.send_multiple(end)

    def play_progression(self, progression):
        print "Playing progression", [midi_note(x[0]) for x in progression]
        bars = len(progression)
        for index in range(bars):
            print "Playing:", midi_notes[progression[index][0]],
            print "    Chord:",
            for note in progression[index]:
                print midi_notes[note],
            try:
                print "    Next Chord:", midi_notes[progression[index+1][0]]
            except:
                print "    End"
            for i in range(4):
                self.play_chord(progression[index])

def frange(start,step,stop):
    step *= 2*((stop>start)^(step<0))-1
    return [start+i*step for i in range(int((stop-start)/step))]

def interpolate(func, items, length=None):
    start = min(items)
    stop = max(items)
    if length is None:
        length = len(items)
    step = (stop - start) / float(length)
    #if step > stop:
    #    step = stop
    if start is 0:
        start = 0.1
    return func(start, step, stop)

def linear(start, step, stop):
    return frange(start, step, stop)

def logarithmic(start, step, stop):
    from math import log
    return [log(x, 2)*(10/log(10, 2)) for x in frange(start, step, stop)]

def exponential(start, step, stop):
    return [(y / (stop - start)) for y in [x*x for x in frange(start, step, stop)]]

class LiveMode(object):
    def __init__(self, chords=None, instruments=None):
        self.chords = chords or []
        self.instruments = instruments or []

class Sequence(object):
    def __init__(self, chords=None, instruments=None):
        self.chords = chords or []
        self.instruments = instruments or []

class Note(object):
    def __init__(self, note, octave=None):
        self.note = note
        self.octave = octave or 4
        self.midi = self.to_midi(note, octave)

    def to_midi(self, note, octave):
        return

def flat_five(chord):
    chord[2] = chord[2] - 1

def drop_five(chord):
    chord.pop(2)

def invert(chord):
    return chord[1:] + chord[:1]

def add9(chord):
    return chord.append(min(chord) + 15)

def add11(chord):
    return chord.append(min(chord) + 18)

class Interval:
    unison = 0
    min_2nd = dim_2nd = 1
    second = maj_2nd = 2
    min_3rd = 3
    third = maj_3rd = 4
    fourth = perfect_4th = aug_3rd = 5
    tritone = dim_5th = flat_five = 6
    fifth = perfect_5th = 7
    min_6th = aug_5th = 8
    sixth = maj_6th = 9
    min_7th = aug_6th = 10
    seventh = maj_7th = 11
    octave = 12
    flat_9 = 13
    ninth = 14
    sharp_9 = aug_9th= 15
    eleventh = 16
    thirteenth = 17

class Chord(object):
    def __init__(self, root, intervals=None):
        if len(root.split()) > 1:
            notes = [midi_note(x) for x in root.split()]
            notes.sort()
            self.root_midi = min(notes)
            self.root = midi_notes_joined[self.root_midi].upper()
            self._update([(x - self.root_midi) for x in notes])
        else:
            self.root = root.upper()
            self.root_midi = midi_note(root)
            self.midi = [self.root_midi]
            self.notes = [midi_notes_joined[self.root_midi]]
            self.intervals = [0]
            self.name = root.upper()
        if intervals is not None:
            if type(intervals) is str:
                if hasattr(self, intervals):
                    getattr(self, intervals)()
                else:
                    intervals = intervals.split()
                    self._update(intervals)
            elif type(intervals) is tuple or list:
                self._update(intervals)
        self.permutations = []

    def _determine_name(self):
        return None

    def _update(self, intervals=None):
        if intervals is not None:
            self.intervals = intervals
        self.notes = [midi_notes_joined[self.root_midi + i].upper() for i in self.intervals]
        self.midi = [self.root_midi + interval for interval in self.intervals]
        self.name = "%s (%s)" % (self.root, ' '.join(self.notes))

    def flat_five(self):
        if 7 in self.intervals:
            self.intervals[self.intervals.index(7)] = 6
            self._update()
        return self

    def drop_five(self):
        if 7 in self.intervals:
            self.intervals.pop(self.intervals.index(7))
            self._update()
        return self

    def invert(self):
        self.intervals.sort()
        self._update(self.intervals[1:] + self.intervals[:1])
        return self

    def second_inversion(self):
        self.intervals.sort()
        self._update(self.intervals[2:] + self.intervals[:2])
        return self

    def third_inversion(self):
        if len(self.intervals) > 3:
            self.intervals.sort()
        self._update(self.intervals[3:] + self.intervals[:3])
        return self

    def add9(self):
        if 14 not in self.intervals:
            self.intervals.append(14)
            self._update()
        return self

    def add11(self):
        if 16 not in self.intervals:
            self.intervals.append(16)
            self._update()
        return self

    def add13(self):
        if 17 not in self.intervals:
            self.intervals.append(17)
            self._update()
        return self

    def add(self, interval):
        if type(interval) is str:
            if hasattr(Interval, interval):
                interval = getattr(Interval, interval)
            else:
                interval = midi_note(interval) - self.root_midi
        if interval not in self.intervals:
            self.intervals.append(interval)
            self._update()
        return self

    def augment(self):
        if Interval.fifth in self.intervals:
            self.intervals[self.intervals.index(Interval.fifth)] = Interval.aug_5th
            self._update()
        return self

    def reverse(self):
        self.intervals.reverse()
        self._update()
        return self

    def shuffle(self):
        random.shuffle(self.intervals)
        self._update()
        return self

    def sort(self):
        self.intervals.sort()
        self._update()
        return self

    def __repr__(self):
        return 'Chord - %s' % self.name

    def triad(self):
        self._update([0, 4, 7])
        return self

    def min_triad(self):
        self._update([0, 3, 7])
        return self

    def dim_triad(self):
        self._update([0, 3, 6])
        return self

    def aug_triad(self):
        self._update([0, 4, 8])
        return self

    def seventh(self):
        self._update([0, 4, 7, 10])
        return self

    def maj_7th(self):
        self._update([0, 4, 7, 11])
        return self

    def min_7th(self):
        self._update([0, 4, 7, 10])
        return self

    def dim_7th(self):
        self._update([0, 3, 6, 10])
        return self

    def ninth(self):
        self._update([0, 4, 7, 10, 14])
        return self

    def seventh_flat_five(self): pass
    def min_maj_7th(self): pass
    def maj_6th(self): pass
    def min_6th(self): pass
    def dom_6th(self): pass
    def six_ninth(self): pass
    def min_9th(self): pass
    def maj_9th(self): pass
    def dom_9th(self): pass
    def dom_flat_9th(self): pass
    def dom_sharp_9th(self): pass
    def eleventh(self): pass
    def min_11th(self): pass
    def min_13th(self): pass
    def maj_13th(self): pass
    def dom_13th(self): pass
    def sus_triad(self): pass
    def sus_2nd_triad(self): pass
    def sus_4th_triad(self): pass
    def sus_7th(self): pass
    def sus_4th_9th(self): pass
    def aug_maj_7th(self): pass
    def aug_min_7th(self): pass
    def dom_flat_five(self): pass
    def lydian_dom_7th(self): pass
    def hendrix_chord(self): pass
    def tonic(self): pass
    def tonic7(self): pass
    def supertonic(self): pass
    def supertonic7(self): pass
    def mediant(self): pass
    def mediant7(self): pass
    def subdominant(self): pass
    def subdominant7(self): pass
    def dominant(self): pass
    def dominant7(self): pass
    def submediant(self): pass
    def submediant7(self): pass
    def subtonic(self): pass
    def subtonic7(self): pass

    I, II, III, IV, V, VI = (shift_notes(diatonic, x) for x in range(6))
    ii, iii, vi, vii = (shift_notes(diatonic, x) for x in range(4))
    I7, II7, III7, IV7, V7, VI7 = (shift_notes(diatonic, x) for x in range(6))
    ii7, iii7, vi7 = (shift_notes(diatonic, x) for x in range(3))

#aliases = {
#    'triad': ['maj_triad'],
#    'seventh': ['dom_7th']
#}

#for chord in chords:
#    intervals = chords[chord]
#    def chord_method(self):
#        self.intervals = intervals
#        return self
#    setattr(Chord, chord, chord_method)

class Scale(object):
    def __init__(self, key):
        self.key = key
        self.notes = self.to_notes(key)

    def to_midi(self, key, scale):
        if type(key) is str:
            key = midi_note(key)
        return [interval + key for interval in scale]

    def to_notes(self, key, scale):
        return [Note(x) for x in scale_notes(key, scale)]

    def to_chord(self, intervals, notes=None):
        if notes is None:
            notes = self.notes
        return [midi_note(x) for x in notes if x in intervals]

class Progression(object):
    def __init__(self, key, sequence):
        self.key = key
        self.sequence = self.convert_seq(sequence)


    def to_chords(self, key, chords, changes):
        print "Scale tones",
        for note in chords[:11]: print midi_notes[note],
        print
        chords = []
        print "Chords:"
        for change in changes:
            change -= 1
            print midi_notes[chords[change]] + ":",
            chord = [chords[change + interval] for interval in [0, 2, 4, 6]]
            for note in chord: print midi_notes[note],
            print
            chords.append(chord)
        return chords

def probability_check(value):
    choices = [(1 if x < (value * 100) else 0) for x in range(100)] # build list of choices
    for i in range(10): random.shuffle(choices) # shuffle it a bit
    return random.choice(choices) # decide whether it's played or not

def check_accuracy(value):
    choices = [(1 if x < (value * 100) else 0) for x in range(100)] # build list of choices
    for i in range(10): random.shuffle(choices) # shuffle it a bit
    picked = [random.choice(choices) for x in range(10000)]
    return (sum([x for x in picked if x == 1]) / 10000.0) / value
