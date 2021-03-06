#
# Author: Timo Smieszek
#
# Code used for the Supplementary Information (pp. 2-3) of
#
# Smieszek T, Salathe M. A low-cost method to assess the epidemiological impor-
# tance of individuals in controlling infectious disease outbreaks. BMC Medicine
# 2012, XXX: XXXX.
#
# This code identifies and stores the location (room) of mobile motes. Input are
# the raw mote files. The identification builds on two algorithms: (1) identifi-
# cation of the supposedly closest stationary mote, (2) the smoothing of the
# identified location patterns.
#
# Algorithm 1: The process uses the received information of the mobile mote of
#              interest and the information of adjacent motes. It further uses
#              the (weighted) location information of previous and future time
#              steps.
# Algorithm 2: The second process starts with the location patterns generated by
#              process 1. If one room is A and a second room is B, then ABAA or
#              AABA patterns are turned into AAAA patterns: As the frequency of
#              measurements is 20s, short re-locations of <40s with a following
#              return to the previous room are deemed to be wrong.
#


###########
# Modules #
###########


import sys
import math
import csv
import fileinput


###########
# Classes #
###########


class AllData(object):
    
    def __init__(self):
        self.sequences = {} # {person id --> Sequence}
        self.locations = {} # {person id --> {t --> room id}}
    
    def add_sequence(self, sequence):
        # sequence - a Receiver_sequence object
        
        self.sequences[sequence.receiver_id] = sequence
        self.locations[sequence.receiver_id] = {}
    
    def write_to_files(self,
                       filestub):
        # filestub - path + first part of filename; person id will be added
        
        for i in self.locations:
            filename = filestub + str(i)
            output = open(filename, "w")
            timeline = sorted(self.locations[i].keys())
            for t in timeline:
                r = self.locations[i][t]
                if r == 0:
                    continue
                output.write('%6d%6d\n' % (t,r))
    
    def identify_location(self,
                          i,
                          t,
                          t_w_list):
        # i - person id
        # t - timestamp
        # t_w_list - list of tuples (relative timestamp, relative weight)
        
        THRESHOLD = 3.16 * (10**-9) # This is the power threshold (in mW) below which
                           # stationary mote signals are no longer believed to
                           # have been originated from the room the mobile mote
                           # is in.
        
        # Identify all close mobile notes for all timestamps in t_w_list
        contacts = {}
        for t_w in t_w_list:
            t_cur = t + t_w[0]
            if (t_cur) in self.sequences[i].sequence:
                contacts[t_cur] = ([i] +
                                   self.sequences[i].return_neighbor_ids(t_cur))
        
        # Identify weighted average signal strength per stationary mote
        data = {}
        w_number_datapoints = 0
        for t_cur in contacts:
            for t_w in t_w_list:
                if (t_cur - t_w[0]) == t:
                    weight = t_w[1]
            w_number_datapoints += (len(contacts[t_cur]) * weight)

        for t_cur in contacts:
            data[t_cur] = {}
            # Determine weight
            for t_w in t_w_list:
                if (t_cur - t_w[0]) == t:
                    weight = float(t_w[1])
            # Determine and weight signal strength
            for c in contacts[t_cur]:
                rooms = self.sequences[c].return_nearest_rooms(t_cur)
                for r in rooms.keys():
                    if r in data[t_cur]:
                        data[t_cur][r] = data[t_cur][r] + (rooms[r][0] * weight
                                         / float(w_number_datapoints))
                    else:
                        data[t_cur][r] = (rooms[r][0] * weight
                                         / float(w_number_datapoints))
        
        # Sum up partial signal strenghts
        signals = {}
        for t_cur in data:
            for r in data[t_cur]:
                if not r in signals:
                    signals[r] = 0.0
                signals[r] = signals[r] + data[t_cur][r]
        
        # Find strongest signal; return id 0 if no signal exists
        max_signal = 0.0
        max_id = 0
        for r in signals:
            if signals[r] > max_signal:
                max_id = r
                max_signal = signals[r]
        
        # If strongest signal < threshold, return id 0
        if max_signal < THRESHOLD:
            max_id = 0
        
        # Store stationary mote id and return it
        if not i in self.locations:
            self.locations[i] = {}
        
        self.locations[i][t] = max_id
        if max_id == 10023: print "10023:", i, t
        return max_id
    
    def smooth_location(self,
                        i,
                        t,
                        patterns):
        # i - person id
        # t - timestamp
        # patterns - list of tuples e.g. (True, False, True)
        #            stands for temporal patterns of room occupation
        #            room A = True
        #            room B = False
        
        pattern_exists = 0
        
        for p in patterns:
            
            elements = len(p)
            flag = False
            rooms = []
            r1 = None
            r2 = None
            
            for t_add in range(0, elements):
                
                # Missing data leads to an early termination of loop
                if (t + t_add) in self.locations[i]:
                    rooms.append(self.locations[i][t + t_add])
                else:
                    flag = True
                    break
                
                # Check condition "room at t + t_add should be room 1"
                if p[t_add] == True:
                    if r1 == None:
                        r1 = rooms[-1]      # Room 1 in pattern
                    if not r1 == rooms[-1]:
                        flag = True
                        break
                
                # Check condition "room at t + t_add should be room 2"
                if p[t_add] == False:
                    if r2 == None:
                        r2 = rooms[-1]      # Room 2 in pattern
                    if r2 == r1:
                        flag = True
                        break
                    if not r2 == rooms[-1]:
                        flag = True
                        break
            
            # If pattern was identified, change room B to room A
            if flag == False:
                pattern_exists = 1
                for t_add in range(0, elements):
                    if p[t_add] == False:
                        self.locations[i][t + t_add] = r1
                break
        
        return pattern_exists     # Return 1 if a patterns was found, else 0


class Receiver_sequence(object):
    # Contains a sequence of Signals for a particular receiver
    
    def __init__(self, receiver_id):
        # receiver_id - an integer value
        
        self.receiver_id = receiver_id
        self.sequence = {}
    
    def add_signals(self, signals):
        # signals - Signals object
        
        # Check if object is valid
        if self.receiver_id != signals.receiver_id:
            print "---ERROR---------------------"
            print "Signal belongs to mote", signal.receiver_id
            print "Signal container to mote", self.receiver_id
            sys.exit() # Replace with correctly raised error
        
        # Add signals to sequence
        self.sequence[signals.global_time] = signals
    
    def return_neighbor_ids(self, t):
        # t - timestamp
        
        if t in self.sequence:
            return self.sequence[t].return_neighbor_ids()
        else:
            return []
    
    def return_nearest_rooms(self, t):
        # t - timestamp
        
        if t in self.sequence:
            return self.sequence[t].return_nearest_rooms()
        else:
            return {}


class Signals(object):
    # Contains all Signal_mob and Signal_sta objects of a particular receiver at
    # a particular global time
    
    def __init__(self, global_time, receiver_id):
        # global_time - timestamp; integer value
        # receiver_id - integer value
        
        self.global_time = global_time
        self.receiver_id = receiver_id
        self.mobile = [] # list of all mobile signals
        self.stationary = [] # list of all stationary signals
    
    def add_signal(self, signal):
        # signal - either a Signal_mob or a Signal_sta object
        
        # Check if Signal object fits into Signal_at_time object
        if self.receiver_id != signal.receiver_id:
            print "---ERROR---------------------"
            print "Signal belongs to mote", signal.receiver_id
            print "Signal container to mote", self.receiver_id
            sys.exit() # Replace with correctly raised error
        if self.global_time != signal.global_time:
            print "---ERROR---------------------"
            print "Signal has global time", signal.global_time
            print "Container is for global time", self.global_time
            sys.exit() # Replace with correctly raised error
        
        if signal.TYPE == "mobile":
            if not signal in self.mobile:
                self.mobile.append(signal)
        elif signal.TYPE == "stationary":
            if not signal in self.stationary:
                self.stationary.append(signal)
        else:
            print "---ERROR---------------------"
            print "Unknown type of object"
            sys.exit() # Replace with correltly raised error
    
    def return_neighbor_ids(self):
        neighbors = []
        for n in self.mobile:
            neighbors.append(n.sender_id)
        return neighbors
    
    def return_nearest_rooms(self):
        rooms = {}
        for r in self.stationary:
            rooms[r.sender_id] = (r.power, r.rssi)
        return rooms


class Signal_mob(object):
    # one Signal_mob object contains the id of one particular sending mobile mote
    # and the id of the mobile mote that received the signal
    TYPE = "mobile"
    
    def __init__(self, global_time, receiver_id, sender_id):
        # all integer values
        
        self.global_time = global_time
        self.receiver_id = receiver_id
        self.sender_id = sender_id


class Signal_sta(object):
    # one Signal_sta object contains the id of one particular stationary mote,
    # its signal strength and the id of the mobile mote that received the signal
    TYPE = "stationary"
    
    def __init__(self, global_time, receiver_id, sender_id, signal_strength):
        # all integer values
        
        self.global_time = global_time
        self.receiver_id = receiver_id
        self.sender_id = sender_id
        self.rssi = self.convert_reading_to_rssi(int(signal_strength))
        self.power = self.convert_rssi_to_power(self.rssi)
        
    def convert_rssi_to_power(self, rssi):
        # converts dBm value to mW value (which is no longer logarithmic)
        return 10.0**(float(rssi)/10.0) 
        
    def convert_reading_to_rssi(self, reading):
        # converting a rssi reading to a proper rssi value (in dBm)
        # code comes from Stanford code
        if(reading < 128):
            return reading-45
        else:
            rssi = -1*((reading-1)^(0xFF))-45
            return rssi


#############
# Functions #
#############


def read_person_to_person_data(masterfile):
    """Reads p2p data and returns dict (pers. id --> timestamp --> [pers. ids])
    """
    # masterfile is a file that contains the filenames of all person_to_location
    #            filenames to be read
    
    data = All_data()
    ID_POS = 0 # position of individual id in the master file
    FILE_POS = 1 # position of the corresponding datafilename 
    
    input_file = csv.reader(open(masterfile,'r'))
    for line in input_file:
        receiver_id = int(line[ID_POS])
        filename = line[FILE_POS]
        print "reading ", filename
        data.add_sequence(read_person_to_person_file(filename, receiver_id))
    
    return data

def read_person_to_person_file(filename, receiver_id):
    """Reads p2p data and returns dict (timestamp --> [pers. ids])"""
    # filename of the location data of an individual
    
    ID_POS = 0 # position of recorded mote id in raw mote file
    STRENGTH_POS = 2 # position of signal strength
    T_POS = 4 # position of global time
    
    Timeline_of_Signals = {}
    
    # Read data
    input_file = fileinput.input(filename)
    for line in input_file:
        
        # Prepare data
        data = line.split()
        cur_t = int(data[T_POS])
        cur_id = int(data[ID_POS])
        cur_strength = int(data[STRENGTH_POS])
        
        # If Signals object does not exist for cur_t create
        if not cur_t in Timeline_of_Signals:
            Timeline_of_Signals[cur_t] = Signals(cur_t, receiver_id)
        
        # Create Signal object and store it in Signals object
        if cur_id < 10000:
            Timeline_of_Signals[cur_t].add_signal(
                                         Signal_mob(cur_t, receiver_id, cur_id))
        else:
            Timeline_of_Signals[cur_t].add_signal(
                           Signal_sta(cur_t, receiver_id, cur_id, cur_strength))
    
    # Create a Receiver_sequence object and transfer all Signals objects to it
    seq = Receiver_sequence(receiver_id)
    for t in Timeline_of_Signals:
        seq.add_signals(Timeline_of_Signals[t])
    
    return seq

def convert_mW_to_dBm(power):
    return 10.0 * math.log10(power)


########
# Main #
########


data = read_person_to_person_data("./data/p2pmasterfile.csv")

for i in data.sequences.keys():
    
    print i
    
    # Identify current location of mobile mote based on mote's and neighbors'
    # stationary mote information.
    # 3rd parameter: (timestamp relative to t, relative weight)
    for t in range(600,3000):
        data.identify_location(i,t,[(-2,1),(-1,2),(0,4),(1,2),(2,1)])
    
    # Change AABA and ABAA patterns to AAAA patterns
    cnt = 1
    while cnt > 0:     # Cont. loop if corrections were made in last iteration
        cnt = 0
        for t in range(600,3000):
            cnt += data.smooth_location(i,t,[(True,False,True,True),
                                             (True,True,False,True)])
        print "Corrected", cnt, "patterns"

data.write_to_files("./location_A12/location_node-")

