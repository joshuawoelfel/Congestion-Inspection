# Author: Joshua Woelfel
# jwolf083@mtroyal.ca

from mininet.topo import Topo
from mininet.link import TCLink

# Link configuration presets for Dumbbell topology class. All hosts left of 
# bottleneck will use the link configuration of the first element, 
# the bottleneck link uses the link configuration specified in the 2nd element,
# and all hosts right of the bottleneck will use the link configuration 
# specified by the 3rd element.
LINK_CONFIG = {
  'DB_S': [{
    'bw': 50,
    'delay': '10ms',
    'max_queue_size': 10000
  },
  {
    'bw': 10,
    'delay': '0ms',
    'max_queue_size': 100
  },
  {
    'bw': 50,
    'delay': '0ms',
    'max_queue_size': 10000
  }],
  'DB_L': [{ 
    'bw': 100,
    'delay': '10ms',
    'max_queue_size': 10000
  },
  {
    'bw': 10,
    'delay': '0ms',
    'max_queue_size': 10000

  },
  {
    'bw': 100,
    'delay': '0ms',
    'max_queue_size': 10000
  }]
}

# Dumbbell Class
# Creates a Mininet topology class in the form of a dumbell. Two switches are 
# connected to each others via a bottleneck link,  and each switch has an equal
# number of hosts connected to it 
# TODO: Draw picture:
class Dumbbell(Topo):
  _node_pair_names = []
 
  # Builds the topology with the given link configuration and number of node 
  # pairs on the left and right of the center bottleneck link.

  # lconfig: An array with exactly three link configurations 
  #   - the first element being the link configuration of all links connecting hosts to the switch left of the bottleneck link
  #   - the second element being the link configuration of the bottleneck link connecting the left and right switches together
  #   - the third element being the link configuration of all links connecting hosts to the switch right of the bottleneck link
  #  
  # num_node_pairs: int representing the number of hosts to create left and right of the bottleneck  
  def build(self, lconfig, num_node_pairs=1):
    l_switch = self.addSwitch('s1')
    r_switch = self.addSwitch('s2')
    self.addLink(l_switch, r_switch, cls=TCLink, **lconfig[1])

    for i in range(1, num_node_pairs + 1):
      l_host_name = f"h{i}"
      r_host_name = f"h{num_node_pairs + i}"
      
      self._node_pair_names.append((l_host_name, r_host_name))

      l_host = self.addHost(l_host_name)
      r_host = self.addHost(r_host_name)

      self.addLink(l_host, l_switch, cls=TCLink, **lconfig[0])
      self.addLink(r_switch, r_host, cls=TCLink, **lconfig[2])

  def getNodePairNames(self):
      return self._node_pair_names[:]
    
