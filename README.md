# [Livewire Simple Delegation Switcher](https://mediarealm.com.au/livewire-switcher/)

This application allows you to simply switch between different Livewire Sources (Inputs) and send them to a single Livewire Destination (Output). It's designed to be used as a simple studio delegation switcher. It also supports GPI as inputs (either to switch, or change the button indications), and GPIO Trigger outputs. It runs on Raspberry Pi.

![Livewire Simple Delegation Switcher - Screenshot](https://mediarealm.com.au/wp-content/uploads/2017/07/Livewire-Simple-Delegation-Switcher-Screenshot.png)

You could use the PathfinderPC software. However, most small radio station's don't have the budget to buy this. If all you need to do is switch between a couple of different sources, Pathfinder may seem a little excessive.

This application relies on the Livewire Routing Protocol, so most Axia Livewire devices are supported. To support LWRP, we make use of the following libraries:

* [Livewire Routing Protocol Client](https://github.com/anthonyeden/Livewire-Routing-Protocol-Client)
* [Axia Livewire Stream Address Helper](https://github.com/anthonyeden/Axia-Livewire-Stream-Address-Helper)

This software has been developed by Anthony Eden (https://mediarealm.com.au/). Visit the [official website](https://mediarealm.com.au/livewire-switcher/).

## Getting Started

1. Rename 'config-sample.json' to 'config.json'
2. Edit config.json to meet your needs

 * You'll need to include the IP Address of your Output Node, the physical output number on your Node, and Livewire Channel Numbers for each source

If all has gone well, you'll now be able to switch the source to your destination. The source highlighted in "Red" is the currently active source.

## GPIO Support

There are two ways you can use Livewire GPIO within this app:

1. GPI Inputs
2. GPIO Output Triggers

You can use these two features together, or separately.

### GPI Inputs

You can configure this switcher to be controlled via the GPI pins on a single Livewire device. It's an input - essentially a way of controlling the switcher from external hardware. There's a 1:1 relationship between GPI pins and Switcher Buttons in this app. Whenever a pin is pulled low, the configured button in the lwSDS app is selected, changing the destination audio.

To configure this, configure global options 'GPI_DeviceIP' and 'GPI_DevicePassword', and source options 'GPI_SwitchPort' and 'GPI_SwitchPin'.

If you don't need this option, delete the lines with 'GPI_DeviceIP' and 'GPI_DevicePassword' from the config file.

You can also specify the GPI on a button to only be used as an 'indication' (rather than performing a switch). To do this, set option "GPI_IndicationOnly" to true.

### GPIO Output Triggers

Output Triggers are used to send GPIO changes when a button is selected. Think of it as an output from this app, which is only sent whenever you press a button.

For configuration options, see the file '[config-sample-gpiotriggers.json'](https://github.com/anthonyeden/Livewire-Simple-Delegation-Switcher/blob/master/config-sample-gpiotriggers.json).

Under some circumstances, you may also like to set option "DisableRouteChange" to true to stop button presses from changing actually a route - with this mode enabled, button presses will only trigger the GPIO action (not a route change).

## Raspberry Pi

### Installation

1. [Download and install Raspbian Desktop](https://www.raspberrypi.org/downloads/raspbian/) on your Raspberry Pi
2. Connect to an Ethernet network
3. Open Terminal and run the following commands:

```
pip install pysnmp --break-system-packages
git clone https://github.com/WardWitt/Livewire-Simple-Delegation-Switcher.git
chmod +x Livewire-Simple-Delegation-Switcher/start.sh
echo "~/Livewire-Simple-Delegation-Switcher/start.sh" >> ~/.config/labwc/autostart
cp ~/Livewire-Simple-Delegation-Switcher/config-sample-silence-detect.json ~/Livewire-Simple-Delegation-Switcher/config.json
``` 

4. To edit the configuration, run this command:

```
nano ~/Livewire-Simple-Delegation-Switcher/config.json
```

Press Ctrl + X to close the Nano text editor.
  
6. The Livewire Simple Delegation Switcher should now load automatically whenever you login to your Raspberry Pi (there is a 10 second delay to give the Pi a chance to connect to the network). To start it manually, run the following commands from the terminal:

```
cd ~/Livewire-Simple-Delegation-Switcher/
python LW-Delegation-Switcher.py
```

### Upgrading - Raspberry Pi

1. Open Terminal and run the following commands:

```
cd ~/Livewire-Simple-Delegation-Switcher
git pull
```

## License

This software has been released as open source software. You're free to use and modify this software, but no liability can be accepted by the developer.

Please read the license agreement.

## Contributing

Contributions are welcomed. Feel free to submit a pull request to fix bugs or add additional functionality to this application.
