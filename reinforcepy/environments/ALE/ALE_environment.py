import numpy as np
from scipy.misc import imresize
from reinforcepy.environments import BaseEnvironment
from ale_python_interface import ALEInterface


class ALEEnvironment(BaseEnvironment):
    """
    The :class:`MinimalGameHandler` class takes care of the interface to the ALE and tries to do nothing else. It's
    meant for advanced users who need fine control over every aspect of the process. It has many functions that are simply
    wrappers of the underlying ALE but with pythonic names/usage.

    Parameters
    ----------
    rom : byte string
        Specifies the directory to load the rom from. Must be a byte string: b'dir_for_rom/rom.bin'
    display_screen : boolean
        Default False. Whether or not to show the game. True takes longer to run but can be fun to watch
    step_cap: int
        Default None. Maximum number of steps to run in an episode. Breakout can sometimes not return terminal
        even when game is ended. This fixes that and will return terminal after stepping above this count
    """
    def __init__(self, rom, resize_shape=(84, 84), skip_frame=1, repeat_action_probability=0.0,
                 step_cap=None, loss_of_life_termination=False, loss_of_life_negative_reward=False,
                 grayscale=True, display_screen=False, seed=np.random.RandomState()):
        # set up emulator
        self.ale = ALEInterface()

        if display_screen:
            self.ale.setBool(b'display_screen', True)

        self.ale.setInt(b'frame_skip', skip_frame)
        self.ale.setInt(b'random_seed', seed.randint(0, 9999))
        self.ale.setFloat(b'repeat_action_probability', repeat_action_probability)
        self.ale.setBool(b'color_averaging', False)

        self.ale.loadROM(rom.encode())

        # setup gamescreen object. I think this is faster than recreating an empty each time
        width, height = self.ale.getScreenDims()
        channels = 1 if grayscale else 3
        self.grayscale = grayscale
        self.gamescreen = np.empty((height, width, 1), dtype=np.uint8)

        self.resize_shape = resize_shape
        self.skip_frame = skip_frame
        self.step_cap = step_cap
        self.curr_step_count = 0

        # setup action converter
        # ALE returns legal action indexes, convert these to just numbers
        self.action_inds = self.ale.getMinimalActionSet()

        # setup lives
        self.loss_of_life_negative_reward = loss_of_life_negative_reward
        self.cur_lives = self.ale.lives()
        self.loss_of_life_termination = loss_of_life_termination
        self.life_lost = False

    def reset(self):
        self.ale.reset_game()
        self.cur_lives = self.ale.lives()
        self.life_lost = False
        self.curr_step_count = 0

    def step(self, action):
        self.curr_step_count += 1
        ale_action = self.action_inds[action]
        return self._step(ale_action)

    def _step(self, ale_action):
        if not self.loss_of_life_termination and not self.loss_of_life_negative_reward:
            return self.ale.act(ale_action)
        else:
            rew = self.ale.act(ale_action)
            new_lives = self.ale.lives()
            if new_lives < self.cur_lives:
                # if loss of life is negative reward subtract 1 from reward
                if self.loss_of_life_negative_reward:
                    rew -= 1
                self.cur_lives = new_lives
                self.life_lost = True
            return rew

    def get_state(self):
        if self.grayscale:
            self.gamescreen = self.ale.getScreenGrayscale(self.gamescreen)
        else:
            self.gamescreen = self.ale.getScreenRGB(self.gamescreen)
        # if resize_shape is none then don't resize
        if self.resize_shape is not None:
            # if grayscale we remove the last dimmension (channel)
            if self.grayscale:
                processedImg = imresize(self.gamescreen[:, :, 0], self.resize_shape)
            else:
                processedImg = imresize(self.gamescreen, self.resize_shape)
        return processedImg

    def get_state_shape(self):
        return self.resize_shape

    def get_terminal(self):
        if self.loss_of_life_termination and self.life_lost:
            return True
        elif self.step_cap is not None and self.curr_step_count > self.step_cap:
            return True
        else:
            return self.ale.game_over()

    def get_num_actions(self):
        return len(self.action_inds)
