# Ethernet and the local area network

> Converted from an open source reStructuredText chapter. Source: https://github.com/SystemsApproach/book/blob/main/direct/ethernet.rst.  \
> License: CC BY 4.0. Editorial navigation, page furniture, and footnote links were removed.

# 2.6 Multi-Access Networks

Developed in the mid-1970s by researchers at the Xerox Palo Alto
Research Center (PARC), the Ethernet eventually became the dominant
local area networking technology, emerging from a pack of competing
technologies. Today, it competes mainly with 802.11 wireless networks
but remains extremely popular in campus networks and data centers. The
more general name for the technology behind the Ethernet is Carrier
Sense, Multiple Access with Collision Detect (CSMA/CD).

As indicated by the CSMA name, the Ethernet is a multiple-access
network, meaning that a set of nodes sends and receives frames over a
shared link. You can, therefore, think of an Ethernet as being like a
bus that has multiple stations plugged into it. The “carrier sense” in
CSMA/CD means that all the nodes can distinguish between an idle and a
busy link, and “collision detect” means that a node listens as it
transmits and can therefore detect when a frame it is transmitting has
interfered (collided) with a frame transmitted by another node.

The Ethernet has its roots in an early packet radio network, called
Aloha, developed at the University of Hawaii to support computer
communication across the Hawaiian Islands. Like the Aloha network, the
fundamental problem faced by the Ethernet is how to mediate access to a
shared medium fairly and efficiently (in Aloha, the medium was the
atmosphere, while in the Ethernet the medium was originally a coax
cable). The core idea in both Aloha and the Ethernet is an algorithm
that controls when each node can transmit.

Modern Ethernet links are now largely point to point;
that is, they connect one host to an Ethernet *switch*, or they
interconnect switches. As a consequence, the “multiple access” algorithm
is not used much in today’s wired Ethernets, but a variant is now used in
wireless networks, such as 802.11 networks (also known as Wi-Fi). Due to
the enormous influence of Ethernet, we chose to describe its classic
algorithm here, and then explain how it has been adapted to Wi-Fi in the
next section. We will also discuss Ethernet switches elsewhere. For now,
we’ll focus on how a single Ethernet link works.

Digital Equipment Corporation and Intel Corporation joined Xerox to
define a 10-Mbps Ethernet standard in 1978. This standard then formed
the basis for IEEE standard 802.3, which additionally defines a much
wider collection of physical media over which an Ethernet can operate,
including 100-Mbps, 1-Gbps, 10-Gbps, 40-Gbps, and 100-Gbps versions.

## 2.6.1 Physical Properties

Ethernet segments were originally implemented using coaxial cable of
length up to 500 m. (Modern Ethernets use twisted copper pairs, usually
a particular type known as “Category 5,” or optical fibers, and in some
cases can be quite a lot longer than 500 m.) This cable was similar to
the type used for cable TV. Hosts connected to an Ethernet segment by
tapping into it. A *transceiver*, a small device directly attached to
the tap, detected when the line was idle and drove the signal when the
host was transmitting. It also received incoming signals. The
transceiver, in turn, connected to an Ethernet adaptor, which was
plugged into the host. This configuration is shown in :numref:`Figure
%s <fig-tap>`.

> Scheme in the source: figures/f02-22-9780123850591.png

   Ethernet transceiver and adaptor.

Multiple Ethernet segments can be joined together by *repeaters* (or a
multi-port variant of a repeater, called a *hub*). A
repeater is a device that forwards digital signals, much like an
amplifier forwards analog signals; repeaters do not understand bits or
frames. No more than four repeaters could be positioned between any pair
of hosts, meaning that a classical Ethernet had a total reach of only
2500 m. For example, using just two repeaters between any pair of hosts
supports a configuration similar to the one illustrated in
spine of a building with a segment on each floor.

> Scheme in the source: figures/f02-23-9780123850591.png

   Ethernet repeater, interconnecting segments to form a larger
   collision domain.

Any signal placed on the Ethernet by a host is broadcast over the entire
network; that is, the signal is propagated in both directions, and
repeaters and hubs forward the signal on all outgoing segments.
Terminators attached to the end of each segment absorb the signal and
keep it from bouncing back and interfering with trailing signals. The
original Ethernet specifications used the Manchester encoding scheme
described in an earlier section, while 4B/5B encoding (or the similar
8B/10B) scheme is used today on higher speed Ethernets.

It is important to understand that whether a given Ethernet spans a
single segment, a linear sequence of segments connected by repeaters, or
multiple segments connected in a star configuration, data
transmitted by any one host on that Ethernet reaches all the other
hosts. This is the good news. The bad news is that all these hosts are
competing for access to the same link, and, as a consequence, they are
said to be in the same *collision domain*. The multi-access part of the
Ethernet is all about dealing with the competition for the link that
arises in a collision domain.

## 2.6.2 Access Protocol

We now turn our attention to the algorithm that controls access to a
shared Ethernet link. This algorithm is commonly called the Ethernet’s
*media access control* (MAC). It is typically implemented in hardware on
the network adaptor. We will not describe the hardware *per se*, but
instead focus on the algorithm it implements. First, however, we
describe the Ethernet’s frame format and addresses.

## Frame Format

Each Ethernet frame is defined by the format given in :numref:`Figure
%s <fig-enet-format>`. The 64-bit preamble allows the receiver to
synchronize with the signal; it is a sequence of alternating 0s and 1s.
Both the source and destination hosts are identified with a 48-bit
address. The packet type field serves as the demultiplexing key; it
identifies to which of possibly many higher-level protocols this frame
should be delivered. Each frame contains up to 1500 bytes of data.
Minimally, a frame must contain at least 46 bytes of data, even if this
means the host has to pad the frame before transmitting it. The reason
for this minimum frame size is that the frame must be long enough to
detect a collision; we discuss this more below. Finally, each frame
includes a 32-bit CRC. Like the HDLC protocol described in an earlier
section, the Ethernet is a bit-oriented framing protocol. Note that from
the host’s perspective, an Ethernet frame has a 14-byte header: two
6-byte addresses and a 2-byte type field. The sending adaptor attaches
the preamble and CRC before transmitting, and the receiving adaptor
removes them.

> Scheme in the source: figures/f02-25-9780123850591.png

   Ethernet frame format.

## Addresses

Each host on an Ethernet—in fact, every Ethernet host in the world—has a
unique Ethernet address. Technically, the address belongs to the
adaptor, not the host; it is usually burned into ROM. Ethernet addresses
are typically printed in a form humans can read as a sequence of six
numbers separated by colons. Each number corresponds to 1 byte of the
