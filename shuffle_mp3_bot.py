 # -*- coding: utf-8 -*-
import asyncio
import os
import random
from queue import *

import discord
from discord.ext import commands

"""The base file was the playlist.py from the examples.
All adjustments were made to the Music Class.
The player is for a folder of mp3 files and shuffles the music"""


"""Get Path to Music Folder and set Globals"""
path = os.getcwd()+"\Music\\"
current_song = path+random.choice(os.listdir(path))
queue_forward = Queue()
stack_backward = []
player = None
ctxglob = None
stopped = False




if not discord.opus.is_loaded():
    # the 'opus' library here is opus.dll on windows
    # or libopus.so on linux in the current directory
    # you should replace this with the location the
    # opus library is located in and with the proper filename.
    # note that on windows this DLL is automatically provided for you
    discord.opus.load_opus('opus')

class VoiceEntry:
    def __init__(self, message, player):
        self.requester = message.author
        self.channel = message.channel
        self.player = player

    def __str__(self):
        fmt = '*{0.title}* uploaded by {0.uploader} and requested by {1.display_name}'
        duration = self.player.duration
        if duration:
            fmt = fmt + ' [length: {0[0]}m {0[1]}s]'.format(divmod(duration, 60))
        return fmt.format(self.player, self.requester)

class VoiceState:
    def __init__(self, bot):
        self.current = None
        self.voice = None
        self.bot = bot
        self.play_next_song = asyncio.Event()
        self.songs = asyncio.Queue()
        self.skip_votes = set() # a set of user_ids that voted
        self.audio_player = self.bot.loop.create_task(self.audio_player_task())

    def is_playing(self):
        if self.voice is None or self.current is None:
            return False

        player = self.current.player
        return not player.is_done()

    @property
    def player(self):
        return self.current.player

    def skip(self):
        self.skip_votes.clear()
        if self.is_playing():
            self.player.stop()

    def toggle_next(self):
        self.bot.loop.call_soon_threadsafe(self.play_next_song.set)

    async def audio_player_task(self):
        global player
        global current_song
        while True:
            self.play_next_song.clear()
            self.current = await self.songs.get()
            await self.bot.send_message(self.current.channel, 'Now playing ' + str(self.current))
            self.current.player.start()
            await self.play_next_song.wait()

class Music:
    """Voice related commands.

    Works in multiple servers at once.
    """
    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}

    """Continues to play after finished song"""
    def cont(self):
        global player
        global current_song
        global ctxglob
        global stopped
        global queue_forward
        global stack_backward
        if not stopped:
            if not queue_forward.empty():
                stack_backward.append(current_song)
                current_song = queue_forward.get()
            else:
                stack_backward.append(current_song)
                current_song = path+random.choice(os.listdir(path))
            state = self.get_voice_state(ctxglob.message.server)
            player = state.voice.create_ffmpeg_player(filename = current_song, after= self.cont)
            player.start()
            print ("Playing: "+current_song)
        else:
            state = self.get_voice_state(ctxglob.message.server)
            player = state.voice.create_ffmpeg_player(filename = current_song, after= self.cont)
            player.start()
        stopped = False

    def get_voice_state(self, server):
        state = self.voice_states.get(server.id)
        if state is None:
            state = VoiceState(self.bot)
            self.voice_states[server.id] = state

        return state

    async def create_voice_client(self, channel):
        voice = await self.bot.join_voice_channel(channel)
        state = self.get_voice_state(channel.server)
        state.voice = voice

    def __unload(self):
        for state in self.voice_states.values():
            try:
                state.audio_player.cancel()
                if state.voice:
                    self.bot.loop.create_task(state.voice.disconnect())
            except:
                pass

    @commands.command(pass_context=True, no_pm=True)
    async def join(self, ctx, *, channel : discord.Channel):
        """Joins a voice channel."""
        try:
            await self.create_voice_client(channel)
        except discord.ClientException:
            await self.bot.say('Already in a voice channel...')
        except discord.InvalidArgument:
            await self.bot.say('This is not a voice channel...')
        else:
            await self.bot.say('Ready to play audio in ' + channel.name)

    @commands.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        """Summons the bot to join your voice channel."""
        summoned_channel = ctx.message.author.voice_channel
        if summoned_channel is None:
            await self.bot.say('You are not in a voice channel.')
            return False

        state = self.get_voice_state(ctx.message.server)
        if state.voice is None:
            state.voice = await self.bot.join_voice_channel(summoned_channel)
        else:
            await state.voice.move_to(summoned_channel)

        return True

    """Starts the player. Picks a random song from the Music file and plays it.
    Sets the cont() function to run after the song finishes"""
    @commands.command(pass_context=True, no_pm=True)
    async def play(self, ctx):
        global player
        global current_song
        global ctxglob
        global stopped

        ctxglob = ctx
        current_song = path+random.choice(os.listdir(path))
        state = self.get_voice_state(ctx.message.server)
        player = state.voice.create_ffmpeg_player(filename = current_song, after= self.cont)
        player.start()
        stopped = False

    """Goes to the most recently played song and puts the current song
    in the forward queue. If there are no songs in the stack, then it plays
    curren song again."""
    @commands.command(pass_context=True, no_pm=True)
    async def back(self, ctx):
        global player
        global current_song
        global stopped
        global queue_forward
        global stack_backward
        stopped = True

        if len(stack_backward)>0:
            queue_forward.put(current_song)
            current_song = stack_backward.pop()

            print ("Playing: "+current_song)
        else:
            print ("Stack is Empty")

        player.stop()

        try:
            state.audio_player.cancel()
            del self.voice_states[server.id]
            await state.voice.disconnect()
        except:
            pass

    """Skips to the next song and puts the previous song on the stack.
    If there is a forward queue, it plays from that before getting new songs"""
    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        global player
        global current_song
        global stopped
        global queue_forward
        global stack_backward
        stopped = True
        if not queue_forward.empty():
            stack_backward.append(current_song)
            current_song = queue_forward.get()
        else:
            stack_backward.append(current_song)
            current_song = path+random.choice(os.listdir(path))
        print ("Playing: "+current_song)


        player.stop()

        try:
            state.audio_player.cancel()
            del self.voice_states[server.id]
            await state.voice.disconnect()
        except:
            pass

    @commands.command(pass_context=True, no_pm=True)
    async def volume(self, ctx, value : int):
        """Sets the volume of the currently playing song."""
        global player
        player.volume = value / 100
        await self.bot.say('Set the volume to {:.0%}'.format(player.volume))

    @commands.command(pass_context=True, no_pm=True)
    async def pause(self, ctx):
        """Pauses the currently played song."""
        global player
        player.pause()

    @commands.command(pass_context=True, no_pm=True)
    async def resume(self, ctx):
        """Resumes the currently played song."""
        global player
        player.resume()

    """stop option removed"""

bot = commands.Bot(command_prefix=commands.when_mentioned_or('$'), description='A playlist example for discord.py')
bot.add_cog(Music(bot))

@bot.event
async def on_ready():
    print('Logged in as:\n{0} (ID: {0.id})'.format(bot.user))

bot.run('token')
