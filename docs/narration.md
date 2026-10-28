# Narration

Notes on how a story is generated from its plots while the agent plays it.

## The story is a graph

- A story is one graph of events. Each of its 3–5 plots is a subgraph: the plot's events are its nodes, and its causal edges connect them.
- Each node is an event, stamped with a time and a place in story time. It describes what is happening in the story world at that place at that time.
- The time and the place are written in the event's description, not given as attributes.

## How plots overlap

- In the `.author` schema the plots are completely separate: no edge runs from one plot's event to another plot's event.
- Plots overlap through time and place. Two plots may have events at the same time in different places — on Friday evening Bob is in a café thinking of Alice, while Mark, Alice's current boyfriend, is with Alice at the movies — or at the same time in the same place, even about the same characters.
- An event that coincides with another plot's event says so explicitly in its description: that at that time, in the same place, the other plot's event takes place.
- This correlation in time and place is how the plots overlap: whoever plays the story can find out that another plot exists while following one.

## How the agent moves

- The observer — the agent — traverses the graph. It observes one node at a time; where nodes of different plots overlap in time and place, it observes all of them.
- It decides which edge — which action — to pursue, as the reader of a choose-your-own-adventure story picks an option. Each choice moves the observer along a plot's trajectory, or, where plots overlap, onto another plot's trajectory.
- Time moves forward, so the agent cannot go back to a node and take another of its edges. The exception is a story whose time jumps, as in the film *Memento*; such a jump is a specific kind of connection between nodes.
- The agent can ask for some details about the node it is in, but that is a very limited functionality.

## The narrator

The virtual narrator is given the observer's time and place, and produces the description of the scene there and then.
