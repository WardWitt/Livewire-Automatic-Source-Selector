""" A simple Studio Delegation Switcher for Livewire """

__product__     = "Livewire Simple Delegation Switcher"
__author__      = "Anthony Eden"
__copyright__   = "Copyright 2017-2018, Anthony Eden / Media Realm"
__credits__     = ["Anthony Eden"]
__license__     = "GPL"
__version__     = "1.7.0"

import os, sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/libs")

import json
from LWRPClient import LWRPClient
import AxiaLivewireAddressHelper
import tkinter as tk
import tkinter.messagebox as tkMessageBox
from functools import partial
import math
import requests
import threading

import asyncio
from pysnmp.hlapi.v3arch.asyncio import *

class Application(tk.Frame):

    # A list of all the source select buttons
    sourceButtons = []
    
    # The error message label widget
    errorLabel = None

    # The configurable text to put at the top of the main windows
    titleLabel = "Livewire Simple Delegation Switcher"

    defaultWindowWidth = None
    defaultWindowHeight = None
    defaultWindowPosX = None
    defaultWindowPosY = None

    # Store the Livewire Routing Protocol (LWRP) client connection here
    LWRP = None
    LWRP_GPI = None
    LWRP_GPIO_Triggers = {}

    # Configuration parameters for the communication with the Device
    LWRP_IpAddress = None
    LWRP_PortNumber = 93
    LWRP_Password = None
    LWRP_OutputChannel = None
    LWRP_CurrentOutput = None
    LWRP_Sources = []

    # Configuration parameters for Silence Detection
    LWRP_SilenceDetectEnabled = False
    LWRP_SilenceDuration = 10000
    LWRP_SilenceThreshold = -500

    # Priority auto-switching (choose highest-priority non-silent input)
    PriorityAutoEnabled = False
    PriorityCount = 5
    PriorityStableTime = 5
    PriorityNonSilentSince = {}
    PriorityMonitorThread = None
    PriorityMonitorStop = None
    PriorityCurrentAutoIndex = None

    # Configuration parameters for the communication with the Input GPI Device
    LWRP_GPI_IpAddress = None
    LWRP_GPI_PortNumber = 93
    LWRP_GPI_Password = None

    # How many columns do we want?
    columnNums = 1

    # How many buttons in each column?
    columnButtonsEach = 0

    # How many buttons are in the current column?
    columnCurrentCount = 0

    # Which column are we currently rendering?
    columnCurrentNum = 0

    # Should we automatically check for version updates when the app starts up?
    autoCheckVersion = True

    newVersion = False

    # This is a queue of events to execute in the main GUI thread
    callbackEventQueue = []

    previousInput = 0
    switchReason = "None"

    def __init__(self, master = None):
        # Setup the application and display window
        self.root = tk.Tk()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.resizable(width = True, height = True)
        
        # Setup the application's icon - very important!
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        elif __file__:
            application_path = os.path.dirname(__file__)

        iconfile = os.path.join(application_path, "SwitchIcon.ico")

        try:
            self.root.iconbitmap(iconfile)
        except:
            # We don't care too much if the icon can't be included
            pass

        
        # Setup the main window for the application
        tk.Frame.__init__(self, master)
        self.grid(sticky = tk.N + tk.S + tk.E + tk.W)

        if self.setupConfig() is not True:
            self.setErrorMessage("ERROR: " + str(self.setupConfig()))

        else:
            connectionStatus, connection = self.connectLWRP()

            if connectionStatus is False:
                self.setErrorMessage("ERROR: " + str(connection))
        
        if self.defaultWindowWidth is not None and self.defaultWindowHeight is not None and (self.defaultWindowPosX is None or self.defaultWindowPosY is None):
            self.root.geometry('%dx%d' % (self.defaultWindowWidth, self.defaultWindowHeight))
        elif self.defaultWindowWidth is not None and self.defaultWindowHeight is not None and self.defaultWindowPosX is not None or self.defaultWindowPosY is not None:
            self.root.geometry('%dx%d+%d+%d' % (self.defaultWindowWidth, self.defaultWindowHeight, self.defaultWindowPosX, self.defaultWindowPosY))

        self.setupMainInterface()

        if self.autoCheckVersion is True:
            # Check for version updates in another thread
            threading.Thread(target=self.versionCheck, daemon=True).start()
        
        # Start executing callback events in the main thread
        self.root.after(10, self.callbackMainThreadExecution)

    async def send_input_changed_trap(self, currentInput):
        snmpEngine = SnmpEngine()

        errorIndication, errorStatus, errorIndex, varBinds = await send_notification(
            snmpEngine,
            CommunityData('public', mpModel=1),  # SNMPv2c
            await UdpTransportTarget.create((self.SNMPTrapIP, 162)),
            ContextData(),
            'trap',
            NotificationType(
                ObjectIdentity('1.3.6.1.4.1.65248.2.1')
            ).add_varbinds(
                ('1.3.6.1.4.1.65248.1.1', Integer(currentInput)),   # currentInput
                ('1.3.6.1.4.1.65248.1.2', Integer(self.previousInput)),   # previousInput
                ('1.3.6.1.4.1.65248.1.3', OctetString(self.switchReason))   # switchReason
            )
        )

        if errorIndication:
            print("Error:", errorIndication)

    def setupConfig(self):
        # Reads the 'config.json' file and stores the details in this class
        
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        elif __file__:
            application_path = os.path.dirname(__file__)

        if len(sys.argv) > 1 and os.path.isfile(os.path.join(application_path, sys.argv[1])):
            filename = (os.path.join(application_path, sys.argv[1]))
        else:
            filename = 'config.json'
        
        config = self.setupConfigRead(filename)

        if config is False:
            return "Cannot parse configuration file " + filename

        self.LWRP_IpAddress = config['DeviceIP']
        self.LWRP_OutputChannel = config['DeviceOutputNum']

        if "DevicePassword" in config and config['DevicePassword'] is not None:
            self.LWRP_Password = config['DevicePassword']

        if "Title" in config:
            self.titleLabel = config['Title']

        if "DefaultWindowWidth" in config and "DefaultWindowHeight" in config:
            self.defaultWindowWidth = int(config['DefaultWindowWidth'])
            self.defaultWindowHeight = int(config['DefaultWindowHeight'])
        
        if "DefaultWindowPosX" in config and "DefaultWindowPosY" in config:
            self.defaultWindowPosX = int(config['DefaultWindowPosX'])
            self.defaultWindowPosY = int(config['DefaultWindowPosY'])

        if "CheckUpdatesAuto" in config and config['CheckUpdatesAuto'] is False:
            self.autoCheckVersion = False

        if "GPI_DeviceIP" in config and config['GPI_DeviceIP'] is not None:
            self.LWRP_GPI_IpAddress = config['GPI_DeviceIP']

        if "GPI_DevicePassword" in config and config['GPI_DevicePassword'] is not None:
            self.LWRP_GPI_Password = config['GPI_DevicePassword']

        if "SilenceDetectEnabled" in config and config['SilenceDetectEnabled'] is True:
            self.LWRP_SilenceDetectEnabled = True

        if "SilenceDuration" in config:
            self.LWRP_SilenceDuration = int(config['SilenceDuration'])

        if "SilenceThreshold" in config:
            self.LWRP_SilenceThreshold = int(config['SilenceThreshold'])

        if "PriorityAutoEnabled" in config and config['PriorityAutoEnabled'] is True:
            self.PriorityAutoEnabled = True

        if "PriorityCount" in config:
            try:
                self.PriorityCount = int(config['PriorityCount'])
            except:
                pass

        if "PriorityStableTime" in config:
            try:
                self.PriorityStableTime = int(config['PriorityStableTime'])
            except:
                pass

        if "SNMPTrapRX" in config:
            self.SNMPTrapIP = config['SNMPTrapRX']

        for source in config['Sources']:
            if source['SourceNum'][:4] == "sip:":
                self.LWRP_Sources.append(
                    {
                        "ButtonLabel": source['Name'],
                        "LWNumber": None,
                        "LWMulticastNumber": None,
                        "LWSipAddress": source['SourceNum'],
                        "GPIOTriggers": [],
                        "DisableRouteChange": False,
                        "GPI_IndicationOnly": False,
                        "Silence": False
                    }
                )
            else:
                self.LWRP_Sources.append(
                    {
                        "ButtonLabel": source['Name'],
                        "LWNumber": int(source['SourceNum']),
                        "LWMulticastNumber": AxiaLivewireAddressHelper.streamNumToMulticastAddr(source['SourceNum']),
                        "LWSipAddress": None,
                        "GPIOTriggers": [],
                        "DisableRouteChange": False,
                        "GPI_IndicationOnly": False,
                        "Silence": False
                    }
                )

            if "GPI_SwitchPort" in source and "GPI_SwitchPin" in source:
                if int(source['GPI_SwitchPin']) >= 1 and int(source['GPI_SwitchPin']) <= 5:
                    self.LWRP_Sources[-1]['GPI_Port'] = int(source['GPI_SwitchPort'])
                    self.LWRP_Sources[-1]['GPI_Pin'] = int(source['GPI_SwitchPin']) - 1

            if "GPI_IndicationOnly" in source and source['GPI_IndicationOnly'] is True:
                self.LWRP_Sources[-1]['GPI_IndicationOnly'] = True

            if "DisableRouteChange" in source and source['DisableRouteChange'] is True:
                self.LWRP_Sources[-1]['DisableRouteChange'] = True

            if "TriggerGPIO" in source:
                for trigger in source['TriggerGPIO']:
                    if "DeviceIP" not in trigger or "Type" not in trigger or "Port" not in trigger or "Pin" not in trigger or "State" not in trigger :
                        print ("GPIO trigger has not been setup correctly")
                        continue
                    
                    if trigger['Type'] != "GPO" and trigger['Type'] != "GPI":
                        print ("GPIO Trigger Type must be 'GPO' or 'GPI'")
                        continue
                    
                    if trigger['State'] != "low" and trigger['State'] != "high":
                        print ("GPIO Trigger State must be 'low' or 'high'")
                        continue

                    if trigger['DeviceIP'] not in self.LWRP_GPIO_Triggers:
                        self.LWRP_GPIO_Triggers[trigger['DeviceIP']] = {
                            "Connection": None,
                            "DeviceIP": trigger['DeviceIP'],
                            "DevicePort": 93,
                            "DevicePassword": ""
                        }

                        if "DevicePassword" in trigger:
                            self.LWRP_GPIO_Triggers[trigger['DeviceIP']]["DevicePassword"] = trigger['DevicePassword']

                    self.LWRP_Sources[-1]['GPIOTriggers'].append({
                        "DeviceIP": trigger['DeviceIP'],
                        "Type": trigger['Type'],
                        "Port": int(trigger['Port']),
                        "Pin": int(trigger['Pin']),
                        "State": trigger['State']
                    })

                    if "Momentary" in trigger:
                        self.LWRP_Sources[-1]['GPIOTriggers'][-1]['Momentary'] = int(trigger['Momentary'])

        if "Columns" in config:
            self.columnNums = int(config['Columns'])
            self.columnButtonsEach = int(math.ceil(len(self.LWRP_Sources) / self.columnNums))
        
        return True
    
    def setupConfigRead(self, filename):
        
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        elif __file__:
            application_path = os.path.dirname(__file__)

        filename = os.path.join(application_path, filename)
        
        try:
            Config_JSON = open(filename).read()
            return json.loads(Config_JSON)
        
        except Exception as e:
            print ("EXCEPTION:", e)
            return False

    def connectLWRP(self):
        # Tries to establish a connection to the LWRP on the specified device
        
        try:
            self.LWRP = LWRPClient(self.LWRP_IpAddress, self.LWRP_PortNumber)
        except Exception as e:
            print ("EXCEPTION:", e)
            return (False, "Cannot connect to LiveWire device")
        
        try:
            self.LWRP.login(self.LWRP_Password)
        except Exception as e:
            print ("EXCEPTION:", e)
            return (False, "Cannot login to device")

        # Find the current status of the output
        destinationList = self.LWRP.destinationData()

        # Set silence detection if enabled in the config
        if self.LWRP_SilenceDetectEnabled is True:
            # Collect unique input numbers from configured sources
            used_inputs = set()
            for source in self.LWRP_Sources:
                if source['LWNumber'] is not None:
                    used_inputs.add(source['LWNumber'])
            
            # Set silence thresholds only for used inputs
            for input_num in sorted(used_inputs):
                self.LWRP.setSilenceThreshold("in", input_num, self.LWRP_SilenceThreshold, self.LWRP_SilenceDuration)

            self.LWRP.levelAlertSub(self.callbackLevelAlertLWRP)
    
        self.LWRP_CurrentOutput = self.findOutputLWRP(destinationList, self.LWRP_OutputChannel)

        self.LWRP.destinationDataSub(self.callbackOutputsLWRP)

        if self.LWRP_IpAddress == self.LWRP_GPI_IpAddress:
            # Reuse audio destination LWRP device for GPI
            self.LWRP_GPI = self.LWRP
        elif self.LWRP_GPI_IpAddress is not None:
            try:
                # Create new connection for GPI device
                self.LWRP_GPI = LWRPClient(self.LWRP_GPI_IpAddress, self.LWRP_GPI_PortNumber)
            except Exception as e:
                print ("EXCEPTION:", e)
                return (False, "Cannot connect to GPI LiveWire device")
            
            try:
                self.LWRP_GPI.login(self.LWRP_GPI_Password)
            except Exception as e:
                print ("EXCEPTION:", e)
                return (False, "Cannot login to GPI device")

        if self.LWRP_GPI is not None:
            self.LWRP_GPI.GPIDataSub(self.callbackSwitcherGPI)
        
        for device in self.LWRP_GPIO_Triggers:
            try:
                # Create new connection for GPI device
                self.LWRP_GPIO_Triggers[device]['Connection'] = LWRPClient(self.LWRP_GPIO_Triggers[device]['DeviceIP'], self.LWRP_GPIO_Triggers[device]['DevicePort'])
            except Exception as e:
                print ("EXCEPTION:", e)
                print ("Cannot connect to GPIO Trigger LiveWire device:", device)
            
            try:
                self.LWRP_GPIO_Triggers[device]['Connection'].login(self.LWRP_GPIO_Triggers[device]['DevicePassword'])
            except Exception as e:
                print ("EXCEPTION:", e)
                print ("Cannot login to GPIO Trigger device:", device)

        # Start priority monitor if configured
        try:
            self.startPriorityMonitor()
        except:
            pass

        return (True, self.LWRP)

    def startPriorityMonitor(self):
        if self.PriorityAutoEnabled is not True:
            return

        # Initialize tracking state
        self.PriorityNonSilentSince = {}
        self.PriorityCurrentAutoIndex = None
        self.PriorityMonitorStop = threading.Event()
        self.PriorityMonitorThread = threading.Thread(target=self.priorityMonitorLoop, daemon=True)
        self.PriorityMonitorThread.start()

    def stopPriorityMonitor(self):
        if self.PriorityMonitorStop is not None:
            self.PriorityMonitorStop.set()
            try:
                if self.PriorityMonitorThread is not None and self.PriorityMonitorThread.is_alive():
                    self.PriorityMonitorThread.join(timeout=1)
            except:
                pass

    def priorityMonitorLoop(self):
        # Monitors first N priority sources and chooses highest-priority non-silent
        import time
        while not (self.PriorityMonitorStop is not None and self.PriorityMonitorStop.is_set()):
            now = time.time()

            # Only operate when silence detection is enabled and sources exist
            if not self.LWRP_SilenceDetectEnabled:
                time.sleep(0.5)
                continue

            candidate_index = None

            for i in range(0, min(self.PriorityCount, len(self.LWRP_Sources))):
                src = self.LWRP_Sources[i]

                # Consider only sources which have silence info (LWNumber)
                if 'Silence' not in src or src['Silence'] is None:
                    # No info yet
                    if i in self.PriorityNonSilentSince:
                        del self.PriorityNonSilentSince[i]
                    continue

                # src['Silence'] == True means silent; False means non-silent
                if src['Silence'] is False:
                    # mark non-silent time
                    if i not in self.PriorityNonSilentSince:
                        self.PriorityNonSilentSince[i] = now
                else:
                    if i in self.PriorityNonSilentSince:
                        del self.PriorityNonSilentSince[i]

                if i in self.PriorityNonSilentSince:
                    candidate_index = i
                    break

            # If we have a candidate and it's been non-silent for stable time, switch
            if candidate_index is not None:
                started = self.PriorityNonSilentSince.get(candidate_index, None)
                if started is not None and (now - started) >= float(self.PriorityStableTime):
                    # Only switch if different from current auto-choice
                    if self.PriorityCurrentAutoIndex != candidate_index:
                        # Schedule switch on main thread
                        self.callbackEventQueue.append(lambda idx=candidate_index: self.sourceBtnPress(idx, trigger='Auto-switch'))
                        self.PriorityCurrentAutoIndex = candidate_index
                        self.switchReason = 'Auto-switch'
            time.sleep(0.5)

    def findOutputLWRP(self, destinationList, destinationNumber):
        # Find the current output stream number for the specified output
        for destination in destinationList:
            if int(destination['num']) == destinationNumber and destination['attributes']['address'] is not None and destination['attributes']['address'][:4] == "sip:":
                # The active output, in Livewire SIP format
                return destination['attributes']['address']

            if int(destination['num']) == destinationNumber and destination['attributes']['address'] is not None and "." in destination['attributes']['address']:
                # The active output, in Multicast IP Address format
                return AxiaLivewireAddressHelper.multicastAddrToStreamNum(destination['attributes']['address'])
            
            elif int(destination['num']) == destinationNumber and destination['attributes']['address'] is not None and "." not in destination['attributes']['address']:
                # The active output, in Livewire Stream Number format
                return destination['attributes']['address']

            elif int(destination['num']) == destinationNumber:
                return None

        return False

    def callbackOutputsLWRP(self, data):
        # Find the current status of the output
        newSource = self.findOutputLWRP(data, self.LWRP_OutputChannel)
        if newSource is not None and newSource is not False:
            self.LWRP_CurrentOutput = newSource

        # Attach this event back to the main thread
        self.callbackEventQueue.append(self.sourceBtnUpdate)

    def callbackSwitcherGPI(self, data):
        # Perform source switching based on a GPI
        for sourceNum, source in enumerate(self.LWRP_Sources):
            if "GPI_Port" in source and "GPI_Pin" in source and source["GPI_Port"] == int(data[0]['num']):
                if source['GPI_IndicationOnly'] is False and data[0]['pin_states'][source['GPI_Pin']]['state'] == "low":
                    # Switch when the specified pin is low
                    self.callbackEventQueue.append(lambda: self.sourceBtnPress(sourceNum, trigger='GPI'))
                    self.switchReason = 'GPI'
                    return True

                elif source['GPI_IndicationOnly'] is True:
                    if len(self.sourceButtons) >= sourceNum + 1:
                        # Change the indication only on an existing button - no source change
                        button = self.sourceButtons[sourceNum]
                        if data[0]['pin_states'][source['GPI_Pin']]['state'] == "low":
                            button.config(bg = "#FF0000", fg = "#FFFFFF", activebackground = "#FF0000", activeforeground = "#FFFFFF")
                        else:
                            button.config(bg = "#FFFFFF", fg = "#000000", activebackground = "#EEEEEE", activeforeground = "#000000")
    
    def callbackMainThreadExecution(self):
        # We need to execute our callback events from the main thread
        deleteEvents = []

        # Loop and execute events
        for eventI, event in enumerate(self.callbackEventQueue):
            event()
            deleteEvents.append(event)
        
        # Delete events that we've executed
        self.callbackEventQueue[:] = [x for x in self.callbackEventQueue if x not in deleteEvents]
        
        self.root.after(10, self.callbackMainThreadExecution)

    def callbackLevelAlertLWRP(self, alertData):
        for num, sourceAlert in enumerate(alertData):
            for sourceNum, sourceData in enumerate(self.LWRP_Sources):
                if(self.LWRP_Sources[sourceNum]['LWNumber']) == int(sourceAlert['num']):
                    self.LWRP_Sources[sourceNum]['Silence'] = sourceAlert['attributes']['silence']

        self.callbackEventQueue.append(self.sourceBtnUpdate)

    def setupMainInterface(self):
        # Setup the interface with a list of source select buttons

        self.top = self.winfo_toplevel()
        self.top.rowconfigure(0, weight = 1)
        self.top.columnconfigure(0, weight = 1)
        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)
        
        if self.columnNums > 1:
            wrap = None
        else:
            wrap = 400

        # Title Label
        titleLabel = tk.Label(
            self,
            text = str(self.titleLabel),
            font = ("Arial", 24, "bold"),
            wraplength = wrap
        )
        titleLabel.grid(
            column = 0,
            columnspan = self.columnNums,
            row = 0,
            sticky = ("N", "S", "E", "W"),
            padx = 50,
            pady = 5
        )

        # Create the label widget for error messages
        self.setErrorMessage()

        # Create the main menu
        menubar = tk.Menu()
        menubar.add_command(label = "About", command = self.about)
        menubar.add_command(label = "Updates", command = self.updates)
        menubar.add_command(label = "Quit!", command = self.close)
        self.top.config(menu = menubar)

        self.sourceBtnUpdate()

    def sourceBtnUpdate(self):
        # Update the status of all the source buttons on screen
        for sourceNum, sourceData in enumerate(self.LWRP_Sources):
            self.top.rowconfigure(self.columnCurrentCount + 1, weight = 1, pad = 20)
            if len(self.sourceButtons) >= sourceNum + 1:
                # Modify an existing button
                button = self.sourceButtons[sourceNum]

            else:
                # Setup a new button
                button = tk.Button(
                    self,
                    text = sourceData['ButtonLabel'],
                    font = ("Arial", 18, "bold"),
                    command = partial(self.sourceBtnPress, sourceNum)
                )

                # Assign the button to the grid
                button.grid(
                    column = self.columnCurrentNum,
                    row = self.columnCurrentCount + 1,
                    sticky = ("N", "S", "E", "W"),
                    padx = 50,
                    pady = 5
                )

                self.columnCurrentCount += 1

                if self.columnCurrentCount >= self.columnButtonsEach and self.columnCurrentNum < self.columnNums - 1:
                    self.columnCurrentCount = 0
                    self.columnCurrentNum += 1

                self.sourceButtons.append(button)

            if sourceData['Silence'] is True:
                button.config(text=sourceData['ButtonLabel'] + ' - ' + 'Silence!')
            else:
                button.config(text=sourceData['ButtonLabel'])

            if sourceData['GPI_IndicationOnly'] is True:
                # If we're only using this button for indications, don't change the colour here
                pass
            elif sourceData['LWSipAddress'] is not None and self.LWRP_CurrentOutput == sourceData['LWSipAddress']:
                # This channel is currently selected - SIP
                button.config(bg = "#FF0000", fg = "#FFFFFF", activebackground = "#FF0000", activeforeground = "#FFFFFF")
            elif sourceData['LWNumber'] is not None and self.LWRP_CurrentOutput == sourceData['LWNumber']:
                # This channel is currently selected - multicast
                button.config(bg = "#FF0000", fg = "#FFFFFF", activebackground = "#FF0000", activeforeground = "#FFFFFF")
            else:
                # This channel is not currently selected
                button.config(bg = "#FFFFFF", fg = "#000000", activebackground = "#EEEEEE", activeforeground = "#000000")
    
    def sourceBtnPress(self, sourceNum, trigger='manual'):
        self.switchReason = trigger
        # Immediatly trigger a change to the destination/output
        if self.LWRP_Sources[sourceNum]['DisableRouteChange'] is True:
            # This button doesn't need to actually change any LWRP routes
            pass

        elif self.LWRP is None:
            # No active connection to LWRP Device
            self.setErrorMessage("Cannot change destination to button #"+str(sourceNum)+" - no connection to LWRP Device ")

        elif self.LWRP_Sources[sourceNum]['LWSipAddress'] is not None:
            # Sip-based addressing
            self.LWRP.setDestination(self.LWRP_OutputChannel, self.LWRP_Sources[sourceNum]['LWSipAddress'])

        elif self.LWRP_Sources[sourceNum]['LWMulticastNumber'] is not None:
            # Multicast-based addressing
            self.LWRP.setDestination(self.LWRP_OutputChannel, self.LWRP_Sources[sourceNum]['LWMulticastNumber'])
            currentInput = self.LWRP_Sources[sourceNum]['LWNumber']
            # Issue SNMP Trap
            asyncio.run(self.send_input_changed_trap(currentInput))
            self.previousInput = self.LWRP_Sources[sourceNum]['LWNumber']

        else:
            # Invalid address
            self.setErrorMessage("Cannot change destination - Invalid source number specified for button #" + str(sourceNum))
        
        # Trigger GPIO on source changes
        for trigger in self.LWRP_Sources[sourceNum]['GPIOTriggers']:
            if self.LWRP_GPIO_Triggers[trigger['DeviceIP']]['Connection'] is not None and trigger['Type'] == "GPO":
                self.LWRP_GPIO_Triggers[trigger['DeviceIP']]['Connection'].setGPO(trigger['Port'], trigger['Pin'], trigger['State'])

                if "Momentary" in trigger and trigger['State'] == "high":
                    # Handle momentary latching of high GPO triggers
                    self.root.after(trigger['Momentary'] * 1000, lambda: self.LWRP_GPIO_Triggers[trigger['DeviceIP']]['Connection'].setGPO(trigger['Port'], trigger['Pin'], "low"))
                elif "Momentary" in trigger and trigger['State'] == "low":
                    # Handle momentary latching of low GPO triggers
                    self.root.after(trigger['Momentary'] * 1000, lambda: self.LWRP_GPIO_Triggers[trigger['DeviceIP']]['Connection'].setGPO(trigger['Port'], trigger['Pin'], "high"))

            elif self.LWRP_GPIO_Triggers[trigger['DeviceIP']]['Connection'] is not None and trigger['Type'] == "GPI":
                self.LWRP_GPIO_Triggers[trigger['DeviceIP']]['Connection'].setGPI(trigger['Port'], trigger['Pin'], trigger['State'])

                if "Momentary" in trigger and trigger['State'] == "high":
                    # Handle momentary latching of high GPI triggers
                    self.root.after(trigger['Momentary'] * 1000, lambda: self.LWRP_GPIO_Triggers[trigger['DeviceIP']]['Connection'].setGPI(trigger['Port'], trigger['Pin'], "low"))
                elif "Momentary" in trigger and trigger['State'] == "low":
                    # Handle momentary latching of low GPI triggers
                    self.root.after(trigger['Momentary'] * 1000, lambda: self.LWRP_GPIO_Triggers[trigger['DeviceIP']]['Connection'].setGPI(trigger['Port'], trigger['Pin'], "high"))

            else:
                print ("Cannot set GPIO Trigger for source number", sourceNum)

    def setErrorMessage(self, message = None, mode = "replace"):
        # Error Message Label
        
        if self.errorLabel is None:
            if message == None:
                message = "No errors reported..."
            
            self.errorLabel = tk.Label(
                self,
                text = message,
                font = ("Arial", 8, "italic"),
                wraplength = 400
            )
            self.errorLabel.grid(
                column = 0,
                columnspan = self.columnNums,
                row = 100,
                sticky = ("N", "S", "E", "W"),
                padx = 50,
                pady = 5
            )

        elif mode == "replace":
            self.errorLabel.config(text = message)
        elif mode == "append":
            self.errorLabel.config(text = self.errorLabel.cget("text") + "\r\n" + message)

    def about(self):
        variable = tkMessageBox.showinfo('Livewire Simple Delegation Switcher', 'Livewire Simple Delegation Switcher\nCreated by Anthony Eden (http://mediarealm.com.au/)\nVersion: ' + __version__)

    def close(self):
        # Terminate the application
        # Stop priority monitor thread if running
        try:
            self.stopPriorityMonitor()
        except:
            pass
        if self.LWRP is not None:
            self.LWRP.stop()
        
        if self.LWRP_GPI is not None:
            self.LWRP_GPI.stop()
        
        for trigger in self.LWRP_GPIO_Triggers:
            if self.LWRP_GPIO_Triggers[trigger]['Connection'] is not None:
                self.LWRP_GPIO_Triggers[trigger]['Connection'].stop()
        
        self.root.destroy()

    def updates(self):
        if self.autoCheckVersion is False:
            # Send a check for new updates
            self.versionCheck("popup")

        elif self.newVersion is True:
            variable = tkMessageBox.showinfo('Software Updates', 'You currently have version v' + __version__ + '\r\nVersion v' + self.newVersionNum + ' is available\r\nDownload website: ' + self.newVersionURL)
        else:
            variable = tkMessageBox.showinfo('Software Updates', 'You currently have the latest version v ' + __version__)

    def versionCheck(self, mode = "toolbar"):
        # This simple version checker will prompt the user to update if required
        r_data = {
            'version': __version__,
            'product': __product__
        }

        try:
            r_version = requests.post("http://api.mediarealm.com.au/versioncheck/", data = r_data)
            r_version_response = r_version.json()

            self.autoCheckVersion = True

            if r_version_response['status'] == "update-available" and mode == "toolbar":
                self.setErrorMessage(r_version_response['message'], "append")
                self.newVersion = True
                self.newVersionNum = r_version_response['version_latest']
                self.newVersionText = r_version_response['message']
                self.newVersionURL = r_version_response['url_download']

            elif r_version_response['status'] == "update-available" and mode == "popup":
                self.newVersion = True
                self.newVersionNum = r_version_response['version_latest']
                self.newVersionText = r_version_response['message']
                self.newVersionURL = r_version_response['url_download']
                self.updates()
            
            elif mode == "popup":
                self.newVersion = False
                self.updates()
            
            else:
                self.newVersion = False
            
        except Exception as e:
            print ("ERROR Checking for Updates:", e)

if __name__ == "__main__":
    app = Application()
    app.master.title('Livewire Simple Delegation Switcher')
    app.mainloop()
