# Author: Joshua Woelfel
# jwolf083@mtroyal.ca

from mininet.net import Mininet
from mininet.util import dumpNodeConnections, dumpNetConnections

import sys
import subprocess
import time
from time import sleep
import os
import signal
import matplotlib.pyplot as plt
#import parse
import csv
import pandas as pd
import threading

from utils import *
from dumbbell import Dumbbell
from dumbbell import LINK_CONFIG as lc

DEFAULT_RUNTIME = "5"
DEFAULT_LINK_CONFIG = 'DB_S'
DEFAULT_NUM_HOST_PAIRS = 1
DEFAULT_ALGS = []
DEFAULT_DELAYS = [0]

VALID_ALGS = {
  'reno': True,
  'bbr': True,
  'cubic': True
}

# HostPair class
# Provides methods and information on flows between two nodes in the network
class HostPair:
  # Name of directory to which flow information between the nodes is saved
  result_dir = ""
  client_host = None
  server_host = None
  ping_proc = None
  last_iperf_results = ""
  delay = 0
  
  # Constructor: Requires the host that is sending data and the host that is receiving data
  def __init__(self, client_host, server_host):
    self.client_host = client_host
    self.server_host = server_host
    self.result_dir = f"{client_host.name}_{server_host.name}/"
  
  # Starts ping to server_host from client_host if we are not pinging already
  def startPinging(self, base_path):
    if not self.ping_proc == None:
      self.endPinging()

    self.checkDir(base_path)
    self.ping_proc = startPing(
      self.client_host, 
      self.server_host.IP(), 
      f"{base_path}{self.result_dir}ping.txt"
    )

  # Creates the result_dir if it does not exist already.
  # base_path is the path to the directory that will contain result_dir.
  def checkDir(self, base_path):
    complete_path = base_path + self.result_dir
    if not os.path.exists(base_path + self.result_dir):
      os.makedirs(complete_path)
  
  # Sends SIGINT to a running ping_proc  
  def endPinging(self):
    if not self.ping_proc == None:
      self.ping_proc.send_signal(signal.SIGINT)
      self.ping_proc.wait()

  def getClient(self):
    return self.client_host

  # Starts iperf3 server on self.server_host using port s_port, then starts
  # flow from self.client_host for runtime seconds from client using c_port. If
  # delay is specified, will sleep for delay seconds before starting flow. 
  # Returns iperf3 output as string
  def startIperfFlow(self, c_port, s_port, runtime, delay=0):
    server_proc = startIperfServer(self.server_host, s_port)
    self.delay = delay
    if delay > 0:
      time.sleep(delay) 
    self.last_iperf_results = startIperfClient(self.client_host, c_port, self.server_host.IP(), s_port, runtime)
    server_proc.send_signal(signal.SIGINT)
    server_proc.wait()

    return self.last_iperf_results
  
  # Writes the last iperf3 result to disk
  def saveIperfResults(self, base_path):
    checkDir(base_path)
    saveIperfLogs(self.last_iperf_results, f"{base_path}{self.result_dir}iperf.txt")

  def getLastIperfResults(self):
    return self.last_iperf_results
  
  # Calls utils function to parse ftrace file located at ftrace_path using client
  # port: c_port and server port: s_port. If the last iperf3 flow had a delay
  # updates the time values accordingly.
  # Returns the parsed information as as pandas dataframe
  #
  # TODO should refactor to store ports as part of class instead of being passed in
  # TODO have utils function update time values instead?
  def parseFtrace(self, ftrace_path, c_port, s_port):
    ftrace_df = parseFtraceCWND(ftrace_path, self.client_host.IP(), c_port, self.server_host.IP(), s_port)
    ftrace_df['Time'] = [time + self.delay for time in ftrace_df['Time']]

    self.ftrace = ftrace_df
    return self.ftrace

  # Calls utils function to parse ping results located in directory base_path
  # into pandas dataframe.
  # Returns results as pandas dataframe
  def parsePings(self, base_path):
    self.rtt = getRTTs(f"{base_path}{self.result_dir}ping.txt")
    return self.rtt
  
  # Calls utils function to export ping dataframe to csv in result_dir
  def exportCSVPing(self, base_path):
    dfExportCSV(self.rtt, f"{base_path}{self.result_dir}ping.csv")

  # Calls utils function to export ftrace dataframe to csv in result_dir
  def exportCSVFtrace(self, base_path):
    dfExportCSV(self.ftrace, f"{base_path}{self.result_dir}ftrace.csv")

  # Plots ping and ftrace data as a new figure. Saves resulting figure as .png
  # in result_dir
  def plotGraphs(self, plt, base_path):
    fig, (ax1, ax2) = plt.subplots(2)

    ax1.plot(self.rtt['Time'], self.rtt['RTT'])
    ax1.set_title("RTT")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Round-Trip Time (ms)")

    ax2.plot(self.ftrace['Time'], self.ftrace['CWND'])
    ax2.set_title("CWND")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Window Size (segments)")

    fig.suptitle(f"CWND and RTT for {self.client_host.name}-{self.server_host.name} flow") 
    plt.tight_layout()
    plt.savefig(f"{base_path}{self.result_dir}graph.png")
    return plt

# Creates a descriptive name for the base output directory that results are
# saved to. Name is based on congestion algorithm list algs, and the link
# configuration config_name
# Returns descriptive name as string
# 
# TODO make part of utils 
def genDescription(algs, config_name):
  test_type = "" 
  if len(algs) > 1:
    test_type = "multi"
  elif len(algs) == 1:
    test_type = algs[0]
  else:
    test_type = "default"

  return f"{config_name}_{test_type}"

# Main logic for running experiments on a topography. 
#
# topo: Dumbbell topology instance
# algs: list strings of congestion algorithms used by each client host in
#       topo
# runtime: string representing how long to run the tcp flows. Must be 
#          compatible with iperf3 '-t' option (int)
# config_name: name of link configuration defined in Dumbbell class
# delays: list of floating point numbers representing a delay before starting a
#         clients iperf3 flow. 
def testDriverSingle(topo, algs=DEFAULT_ALGS, runtime=DEFAULT_RUNTIME, config_name=DEFAULT_LINK_CONFIG, delays=DEFAULT_DELAYS):
  dump_procs = []
  threads = []
  net = Mininet(topo)
  
  time_secs = int(time.time())

  c_port = '5201'
  s_port = '5001'

  net.start()
  
  print("\nUsing the following node connections: ")
  # Mininet function, prints node connections
  #dumpNodeConnections(net.hosts)
  dumpNetConnections(net)
  # get names of source and destination hosts that will be creating tcp flows
  host_pair_names = topo.getNodePairNames()
  # Build host pairs using Mininet function with host names
  host_pairs = [HostPair(net.get(h_c), net.get(h_s)) for (h_c, h_s) in host_pair_names]

  #TODO implement bandwidth test via user argument
  #testBWD(net, [host_pairs[0].client_host, host_pairs[0].server_host])

  # create list of source hosts from which tcp flows will originate
  seen_clients = set()
  host_clients = [h_p.getClient() for h_p in host_pairs if not (h_p.getClient().name in seen_clients or seen_clients.add(h_p.getClient().name))]

  # calls utils function to create directory where all results for this run 
  # will be stored
  description = genDescription(algs, config_name)
  output_dir = createOutputDir(description)

  # ensure ftrace buffer is not being written to and then clear it
  endFtrace()
  clearFtrace()

  delay_idx = 0
  for host_pair in host_pairs:
    # start ping between host pair
    host_pair.startPinging(output_dir)

    # set delay if delay specified for host pair
    delay = 0
    if delay_idx < len(delays):
      delay = delays[delay_idx]
    
    # append a new thread to our thread list that will call startIperfFlow and 
    # saveIperfResults when executed
    threads.append(threading.Thread(
      target=lambda host_pair=host_pair, delay=delay:(host_pair.startIperfFlow(c_port, s_port, runtime, delay), 
      host_pair.saveIperfResults(output_dir))
    ))
    delay_idx += 1
  
  alg_idx = 0
  for client in host_clients:
    # start tcpdump on source host
    dump_procs.append(startTCPdump(client, f"{output_dir}{client.name}_tcpdump.pcap"))
    
    # set congestion algorithm if specified for host pair
    if alg_idx < len(algs):
      print(f"\nApplying specified congestion algorithm to host {client.name}...")
      print(setCongAlg(client, algs[alg_idx]))
      alg_idx += 1
  
  # enable writing to ftrace buffer by kernel
  startFtrace()

  print("\n**********Starting RTT test with iperf3 (" + runtime + " seconds)**************")
  # execute all threads
  for thread in threads:
    thread.start()
  
  # wait for threads to finish executing
  for thread in threads:
    thread.join()

  print("\nSample result:\n", host_pairs[0].getLastIperfResults())
  
  endFtrace()

  # end tcpdump processes
  for dump_proc in dump_procs:
    dump_proc.send_signal(signal.SIGINT)
    dump_proc.wait()

  for host_pair in host_pairs:
    host_pair.endPinging()
  
  # save full ftrace buffer to file
  ftrace_content = getFtraceLogs()
  ftrace_path = output_dir + 'ftrace_raw.txt'
  saveFtrace(ftrace_content, ftrace_path)

  # save host pair experiment results to file
  for host_pair in host_pairs:
    cwnd_data = host_pair.parseFtrace(ftrace_path, c_port, s_port)
    rtt_data = host_pair.parsePings(output_dir)
    host_pair.exportCSVPing(output_dir)
    host_pair.exportCSVFtrace(output_dir)
    host_pair.plotGraphs(plt, output_dir)

  # show host pair generated graphs
  plt.show()

  # Teardown controllers, switches and hosts. If we crash before tearing down, 
  # mininet will not be able to run. Run "sudo mn" before restarting the program
  # to fix this
  # TODO see if we can automate this at beginning of run
  net.stop()
  print("\n\nResults saved to the following location: " + output_dir)
  

class ArgumentError(Exception):
  def __init__(self, message):
    self.message = message
    super().__init__(message)

# Verifies argument has been passed in with specified option
def optionHasArg(index, args, option):
  no_arg_msg = " flag specified but no argument found. Using default setting. Use -h for more information"
  if index < len(args):
    return True
  else:
    print(option + no_arg_msg)
    return False

# Checks if argument is castable to int
def isInt(arg):
  try: 
    int(arg)
    return True
  except ValueError:
    return False

# Verifies that algorithms are valid
def validateAlgs(algs):
  for alg in algs:
    if not alg in VALID_ALGS:
      return False

  return True

# Verifies that delays are not negative
def validateDelays(delays):
  for delay in delays:
    if delay < 0:
      return False

  return True

# Main logic for error checking user selected options and their arguments.
# Raises ArgumentError if incorrect user input is detected
#
# TODO decompose switch into state array? 
def argParser(args):
  config = {
    'link_config': lc[DEFAULT_LINK_CONFIG],
    'runtime': DEFAULT_RUNTIME,
    'custom' : None,
    'num_host_pairs': DEFAULT_NUM_HOST_PAIRS,
    'algs': DEFAULT_ALGS,
    'lc_name': DEFAULT_LINK_CONFIG,
    'delays': DEFAULT_DELAYS
  }
  
  i = 1
  while i in range(1, len(args)):
    if args[i] == '-l':
      i += 1
      if optionHasArg(i, args, '-l'):
        link_config = args[i]
        if link_config in lc:
          config['link_config'] = lc[link_config]
          config['lc_name'] = link_config
        else:
          raise ArgumentError(f"'{link_config}' is not a valid link configuration. Use -h for more information")

    elif args[i] == '-t':
      i += 1
      if optionHasArg(i, args, '-t'):
        runtime = args[i]
        try: 
          if int(runtime) > 0:
            config['runtime'] = runtime
          else:
            raise ArgumentError(f"'{runtime}' is not a valid runtime. Use -h for more information")
        except ValueError:
          raise ArgumentError(f"'{runtime}' is not a valid runtime. Use -h for more information")
    
    elif args[i] == '-n':
      i += 1
      if optionHasArg(i, args, '-n'):
        try: 
          num_host_pairs = int(args[i])
          if num_host_pairs > 0:
            config['num_host_pairs'] = num_host_pairs
          else:
            raise ArgumentError(f"'{args[i]}' is not a valid number of client/server hosts. Use -h for more information")
        except ValueError:
            raise ArgumentError(f"'{args[i]}' is not a valid number of client/server hosts. Use -h for more information")
    
    elif args[i] == '-a':
      i +=1
      if optionHasArg(i, args, '-a'):
        algs = [alg for alg in args[i].split(',') if not alg == '']
        if validateAlgs(algs):
          config['algs'] = algs
        else:
          raise ArgumentError(f"One or more congestion algorithms in '{args[i]}' is invalid. Use -h to see supported algorithms")

    elif args[i] == '-d':
      i += 1
      if optionHasArg(i, args, '-d'):
        try:
          delays = [float(delay) for delay in args[i].split(',') if not delay == '']
          if validateDelays(delays):
            config['delays'] = delays
          else:
            raise ArgumentError(f"One or more delays in '{args[i]}' is not a valid delay. Use -h for more information")
        except ValueError:
          raise ArgumentError(f"One or more delays in '{args[i]}' is not a valid delay. Use -h for more information")
          

    else:
      raise ArgumentError(f"'{args[i]}' is not a valid option. Use -h for more information")

    

    i += 1

  return config 
          
      
if __name__ == '__main__':
  topo = None
  
  try:
    config = argParser(sys.argv)
    
    #for dubugging
    #print(config)
    
    if config['custom'] == None:
      topo = Dumbbell(config['link_config'], config['num_host_pairs'])
    else:
      topo = config['custom']

    testDriverSingle(topo, config['algs'], config['runtime'], config['lc_name'], config['delays'])
  except ArgumentError as e:
    print(e)

