# Congestion-Inspection
Congestion Inspection is a python-based tool to analyze, inspect, and automate testing of TCP congestion control behavior in emulated network environments using Mininet and Linux-based network performance tools.

## Usage
Download and run as sudo:
```
sudo python3 cinspect.py
```

## Collected Metrics
Each run of cinspect.py will generate a new directory with results for the following: 

**Round Trip Time (RTT):** Congestion Inspection begins by periodically recording the Round Trip Time (RTT) between each host pair using the _ping_ utility.

**TCP Flow Information:** _iperf3_ is used to generate the TCP flow between each host pair. 

**CWND, SSTHRESH, SRTT, etc.:** Linux's ftrace framework is used to collect various internal kernel information like congestion window size using the _tcp__probe_ tracepoint.

**Packet capture:** _tcpdump_ is used to generate packet capture files of each tcp flow.

## Options
**-t** _N_

  specify how long the flow between the host pairs should last
  
**-l** _config_ 

  specify the link configuration to use (see Topology section for more info)

**-n** _N_ 
  
  specify the number of host pairs connected through the center link

**-a** _a1,a2,...,aN_

  specify the congestion control algorithm of the sender of each host pair

**-d** _d1,d2,...,dN_

  specify the delay before each host pair begins its flow

### Mininet Topology
The topology of the network is found in dumbell.py, with the link bandwidths, delays, and buffer sizes customizable using the **LINK_CONFIG** dictionary. Specify the link config using the **-l** option followed by the desired **LINK_CONFIG** key.

## Dependencies
Congestion Inspection was built using [Mininet 2.3.0](https://github.com/mininet/mininet/releases/) using their provided Ubuntu 20.04.1 VM image. See Mininet's install docs for more information.
Additional Linux tools required:
- iperf3
- ping
- tcpdump
- ftrace (tcp_probe tracepoint) based on Ubuntu 20.04.1

Python dependencies:
- pandas
- matplotlib
- parse

## Contributions


## Contact
