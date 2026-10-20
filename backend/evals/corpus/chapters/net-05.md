# Routing in internetworks

> Converted from an open source reStructuredText chapter. Source: https://github.com/SystemsApproach/book/blob/main/internetworking/routing.rst.  \
> License: CC BY 4.0. Editorial navigation, page furniture, and footnote links were removed.

# 3.4 Routing

So far in this chapter we have assumed that the switches and routers
have enough knowledge of the network topology so they can choose the
right port onto which each packet should be output. In the case of
virtual circuits, routing is an issue only for the connection request
packet; all subsequent packets follow the same path as the request. In
datagram networks, including IP networks, routing is an issue for every
packet. In either case, a switch or router needs to be able to look at a
destination address and then to determine which of the output ports is
the best choice to get a packet to that address. As we saw in an earlier
section, the switch makes this decision by consulting a forwarding
table. The fundamental problem of routing is how switches and routers
acquire the information in their forwarding tables.

.. admonition:: Key Takeaway

   We restate an important distinction, which is often neglected,
   between *forwarding* and *routing*. Forwarding consists of
   receiving a packet, looking up its destination address in a table,
   and sending the packet in a direction determined by that table. We
   saw several examples of forwarding in the preceding section. It is
   a simple and well-defined process performed locally at each node,
   and is often referred to as the network's *data plane.* Routing is
   the process by which forwarding tables are built. It depends on
   complex distributed algorithms, and is often referred to as the
   network's *control plane.*  [Next] <key-routing-alg>

While the terms *forwarding table* and *routing table* are sometimes
used interchangeably, we will make a distinction between them here. The
forwarding table is used when a packet is being forwarded and so must
contain enough information to accomplish the forwarding function. This
means that a row in the forwarding table contains the mapping from a
network prefix to an outgoing interface and some MAC information, such
as the Ethernet address of the next hop. The routing table, on the other
hand, is the table that is built up by the routing algorithms as a
precursor to building the forwarding table. It generally contains
mappings from network prefixes to next hops. It may also contain
information about how this information was learned, so that the router
will be able to decide when it should discard some information.

Whether the routing table and forwarding table are actually separate
data structures is something of an implementation choice, but there are
numerous reasons to keep them separate. For example, the forwarding
table needs to be structured to optimize the process of looking up an
address when forwarding a packet, while the routing table needs to be
optimized for the purpose of calculating changes in topology. In many
cases, the forwarding table may even be implemented in specialized
hardware, whereas this is rarely if ever done for the routing table.

table, which tells us that network prefix 18/8 is to be reached by a
next hop router with the IP address 171.69.245.10

.. table:: Example row from a routing table.

   +---------------+---------------+
   | Prefix/Length | Next Hop      |
   +===============+===============+
   | 18/8          | 171.69.245.10 |
   +---------------+---------------+

In contrast, Table %s <tab-ftab> gives an example of a row from a
forwarding table, which contains the information about exactly how to
forward a packet to that next hop: Send it out interface number 0 with
a MAC address of 8:0:2b:e4:b:1:2. Note that the last piece
of information is provided by the Address Resolution Protocol.

.. table:: Example row from a forwarding table.

   +---------------+-----------+-----------------+
   | Prefix/Length | Interface | MAC Address     |
   +===============+===========+=================+
   | 18/8          | if0       | 8:0:2b:e4:b:1:2 |
   +---------------+-----------+-----------------+

Before getting into the details of routing, we need to remind ourselves
of the key question we should be asking anytime we try to build a
mechanism for the Internet: “Does this solution scale?” The answer for
the algorithms and protocols described in this section is “not so much.”
They are designed for networks of fairly modest size—up to a few hundred
nodes, in practice. However, the solutions we describe do serve as a
building block for a hierarchical routing infrastructure that is used in
the Internet today. Specifically, the protocols described in this
section are collectively known as *intradomain* routing protocols, or
*interior gateway protocols* (IGPs). To understand these terms, we need
to define a routing *domain*. A good working definition is an
internetwork in which all the routers are under the same administrative
control (e.g., a single university campus, or the network of a single
Internet Service Provider). The relevance of this definition will become
apparent in the next chapter when we look at *interdomain* routing
protocols. For now, the important thing to keep in mind is that we are
considering the problem of routing in the context of small to midsized
networks, not for a network the size of the Internet.

## 3.4.1 Network as a Graph

Routing is, in essence, a problem of graph theory. :numref:`Figure %s
<fig-graph-route>` shows a graph representing a network. The nodes of
the graph, labeled A through F, may be hosts, switches, routers, or
networks. For our initial discussion, we will focus on the case where
the nodes are routers. The edges of the graph correspond to the
network links. Each edge has an associated *cost*, which gives some
indication of the desirability of sending traffic over that link. A
discussion of how edge costs are assigned is given in a later section.

Note that the example networks (graphs) used throughout this chapter
have undirected edges that are assigned a single cost. This is actually
a slight simplification. It is more accurate to make the edges
directed, which typically means that there would be a pair of edges
between each node—one flowing in each direction, and each with its
own edge cost.

> Scheme in the source: figures/f03-28-9780123850591.png

   Network represented as a graph.

The basic problem of routing is to find the lowest-cost path between
any two nodes, where the cost of a path equals the sum of the costs of
all the edges that make up the path. For a simple network like the one
in Figure %s <fig-graph-route>, you could imagine just
calculating all the shortest paths and loading them into some
nonvolatile storage on each node. Such a static approach has several
shortcomings:

-  It does not deal with node or link failures.

-  It does not consider the addition of new nodes or links.

-  It implies that edge costs cannot change, even though we might
   reasonably wish to have link costs change over time (e.g., assigning
   high cost to a link that is heavily loaded).

For these reasons, routing is achieved in most practical networks by
running routing protocols among the nodes. These protocols provide a
distributed, dynamic way to solve the problem of finding the lowest-cost
path in the presence of link and node failures and changing edge costs.
Note the word *distributed* in the previous sentence; it is difficult to
