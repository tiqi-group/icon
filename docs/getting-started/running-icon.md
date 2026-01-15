{%
    include-markdown "../../README.md"
    start="<!--getting-started-start-->"
    end="<!--getting-started-end-->"
    heading-offset=-1
%}

## Ionpulse
To be able to run experiments, ICON must connect to Ionpulse, the server application running on the control system such QuENCH RFSoC, QuENCH MicroTCA or M-ACTION. Configure the URL or IP and port under Settings -> Hardware.

### Development
If you are testing/developing ICON without the control system, you can use the ionpulse emulator.
See the [Ionpulse sw test README](https://gitlab.phys.ethz.ch/tiqi-projects/ionpulse_sw_test/-/blob/master/README.md) for more info on how to set up the emulator.
