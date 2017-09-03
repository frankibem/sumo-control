# Sumo Control
**Update:** I'm having to work on a different project for my master's so this will be indefinitely suspended. I hope to return to it in future.

My plan is to train a Jumping Sumo minidrone from Parrot to navigate a track using reinforcement learning. This project will be divided into several stages:

- [x] Implement the ARSDK3 protocol in python to allow me control the drone directly via a PC and stream video as well
- [ ] Implement Deep Deterministic Policy Gradient (DDPG) in CNTK (maybe Tensorflow?)
- [ ] Use DDPG to train the drone to navigate a paper track
  - The higher the speed of the robot, the greater the reward
  - Negative rewards for leaving the track. I plan to train a convolutional network to decide whether or not the robot is within the track
  - At each time step, the state will be the last frame (or stack of frames) as well as last read speed from the robot
  - The agents actions will be speed [-100, 100] and turn [-100, 100]


## Requirements
More requirements will be added as the project progresses.

### Software
- Python 3
- OpenCV

### Hardware
- One Jumping Sumo (I am using a Jumping Race Max, other Jumping Drones should also work)
- Several batteries :weary:

## Miscellaneous
- I was able to install OpenCV 3 in my conda environment using: `conda install -c menpo opencv3`
- The minidrone module was adapted from [forthtemple/py-faster-rcnn](https://github.com/forthtemple/py-faster-rcnn) and [haraisao/JumpingSumo-Python
](https://github.com/haraisao/JumpingSumo-Python). As I am only interested in ground motion, I have limited my implementation to that (no jumping, ...)
- The Parrot ARSDK3 document can be found [here](http://developer.parrot.com/docs/bebop/ARSDK_Protocols.pdf). I was also able to find some useful information on their [GitHub](https://github.com/Parrot-Developers) page.
