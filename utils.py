import sys
import subprocess
import time
import os
#import matplotlib.pyplot as plt
#import numpy as np
import parse
import pandas as pd
#import shlex

FTRACE_PATH = "/sys/kernel/debug/tracing"
FTRACE_BUFFER_SIZE_PATH = "/sys/kernel/debug/tracing/buffer_size_kb"

DEFAULT_OUTPUT_DIR = "/home/mininet/results/"

OFFSET_TIME = 3
OFFSET_SRC = 5
OFFSET_DST = 6
OFFSET_CWND = 11
OFFSET_SSTHRESH = 12
OFFSET_SRTT = 14

def setFtraceBuffer(size):
  with open(FTRACE_BUFFER_SIZE_PATH, 'r+') as buffer_size_file:
    line = buffer_size_file.readline()
    
    buffer_size_file.seek(0)
    buffer_size_file.write(str(size))
    buffer_size_file.truncate()

    #words = line.split()
  
    #for word in words:
    #  expanded_val = parse.parse('  

  #return buffer_size
# Creates a unique output directory for a test run using description.
# 
#TODO: don't use constant defined output directory location, instead
# have this be passed as a parameter
def createOutputDir(description):
  full_path = DEFAULT_OUTPUT_DIR + description + '_' + str(int(time.time())) + '/'

  while not checkDir(full_path):
    full_path = DEFAULT_OUTPUT_DIR + description + '_' + str(int(time.time())) + '/'
  
  return full_path

# Checks connectivity between each host in host list using ping
def testRTT(net, hosts):
  for i in range(0,9):
    print(net.pingFull(hosts=hosts))

# Checks bandwidth between each host in host list using iperf
def testBWD(net, hosts):
  print(net.iperf(hosts=hosts, fmt='m', seconds=10, port=5001))

# Parses ping ouput stored as a text file located at ping_out, and converts it
# into a pandas dataframe with a "Time" column and a "RTT" column.
def getRTTs(ping_out):
  f = open(ping_out, 'r')
  
  rtt_vals = []
  line_no = 0
  for line in f:
    if line_no == 0:
      line_no += 1
    else:
      for val in line.split(' '):
        rtt = parse.parse('time={}', val)
        if rtt is not None:
          rtt_vals.append(float(rtt.fixed[0]))

  return pd.DataFrame({'Time': list(range(0, len(rtt_vals))), 'RTT': rtt_vals})
  
# Parses ftrace output stored as a text file located at ftrace_out. Any entries
# with send_ip, send_port, receive_ip, receive_port are extracted and returned
# as a pandas dataframe. Columns include "Time", "SSThresh", "CWND", and "SRTT"
def parseFtraceCWND(ftrace_out, send_ip, send_port, receive_ip, receive_port):
  src = "src={0}:{1}".format(send_ip, send_port)
  dst = "dest={0}:{1}".format(receive_ip, receive_port)

  cwnd_sizes = []
  ssthresh = []
  srtt = []
  times = []
  first_time = None
  with open(ftrace_out, 'r') as ftrace:
    for line in ftrace:
      if len(line) > 0 and line[0] != '#':
        ftrace_items = line.split()
        if ftrace_items[OFFSET_SRC] == src and ftrace_items[OFFSET_DST] == dst:
          # remove text part of CWND reported value
          cwnd_sizes.append(int(ftrace_items[OFFSET_CWND].replace("snd_cwnd=", "")))

          ssthresh.append(int(ftrace_items[OFFSET_SSTHRESH].replace("ssthresh=", "")))

          srtt.append(int(ftrace_items[OFFSET_SRTT].replace("srtt=", "")))
          # remove text part of reported time, set inital starting point to be at time = 0, then record offset in time for follwing times
          time = float(ftrace_items[OFFSET_TIME][:-1])
          if first_time is None:
            first_time = time 
          times.append(time - first_time)

  df = pd.DataFrame({'Time': times, 'SSThresh': ssthresh, 'CWND': cwnd_sizes, 'SRTT': srtt})

  return df


def dfExportCSV(df, path):
  df.to_csv(path, index=False)

def clearFtrace():
  with open('/sys/kernel/debug/tracing/trace', "w") as trace:
    trace.write("")

def endFtrace():
  with open('/sys/kernel/debug/tracing/events/tcp/tcp_probe/enable', "w") as tcp_probe:
    tcp_probe.write("0")

def startFtrace():
  with open("/sys/kernel/debug/tracing/events/tcp/tcp_probe/enable", "w") as tcp_probe:
    tcp_probe.write("1")

def checkDir(path):
  if os.path.exists(path):
    return False
  else:
    os.makedirs(path)
    return True

def startPing(host, dest, path):

  return host.popen('exec /bin/ping {0} > {1}'.format(dest, path), shell=True)
  
def startIperfServer(host, port):

  return host.popen('/bin/iperf3 -s -p ' + port)
  
def startIperfClient(host, c_port, s_ip, s_port, runtime):
  proc = host.popen('/bin/iperf3 --cport {0} -c {1} -V -t {2} -p {3}'.format(c_port, s_ip, runtime, s_port), stdout=subprocess.PIPE)
  
  try:
    outs, errs = proc.communicate(timeout=180)
  except subprocess.TimeoutExpired:
    proc.kill()
    outs, errs = proc.communicate()

  iperf_output = outs.decode('ascii')
 
  return iperf_output

def saveIperfLogs(iperf_logs, path):

  with open(path, "w") as iperf_out:
    iperf_out.write(iperf_logs)


def startTCPdump(host, path):
  # not sure if security vulnerability as injected code could be passed in through path by malicious program if it can somehow access
  # memory and function pointer location
  #command = shlex.split(f"sudo /usr/sbin/tcpdump -w {path}")
  #return subprocess.Popen(command)
  return host.popen(f"/usr/sbin/tcpdump -w {path}")

def setCongAlg(host, alg):
  proc = host.popen('/usr/sbin/sysctl net.ipv4.tcp_congestion_control=' + alg, stdout=subprocess.PIPE)
  
  try:
    outs, errs = proc.communicate(timeout=15)
  except subprocess.TimeoutExpired:
    proc.kill()
    outs, errs = proc.communicate()

  return outs.decode('ascii')

def getFtraceLogs():
  ftrace_content = ""

  with open('/sys/kernel/debug/tracing/trace', "r") as ftrace_orig:
    ftrace_content = ftrace_orig.read()

  return ftrace_content

def saveFtrace(ftrace_content, path):

  with open(path, "w") as ftrace_write:
    ftrace_write.write(ftrace_content)

# deprecated
def plotCWND(graph, cwnd_data):
  graph.plot(cwnd_data['Time'], cwnd_data['CWND'])
  graph.set_title("CWND")
  graph.set_xlabel("Time (s)")
  graph.set_ylabel("Window Size (segments)")

  return graph

# deprecated
def plotRTT(graph, rtt_data):
  graph.plot(rtt_data['Time'], rtt_data['RTT'])
  graph.set_title("RTT")
  graph.set_xlabel("Time (s)")
  graph.set_ylabel("Round-Trip Time (ms)")

  return graph

# deprecated
def plotGraphs(plt, ping_data, cwnd_data, path):
  fig, (ax1, ax2) = plt.subplots(2)

  ax1.plot(ping_data['Time'], ping_data['RTT'])
  ax1.set_title("RTT")
  ax1.set_xlabel("Time (s)")
  ax1.set_ylabel("Round-Trip Time (ms)")
  
  ax2.plot(cwnd_data['Time'], cwnd_data['CWND'])
  ax2.set_title("CWND")
  ax2.set_xlabel("Time (s)")
  ax2.set_ylabel("Window Size (segments)")
  
  plt.tight_layout()
  return plt
  #plt.tight_layout()
  #plt.show()
  #plt.savefig(path)  
